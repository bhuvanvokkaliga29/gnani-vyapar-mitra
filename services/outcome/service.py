"""Service implementation for Phase 9.3 Outcome, Feedback & Recovery Loop.

Contract: outcome-feedback/v1

Orchestrates:
1. Merchant tenant validation.
2. Resolution of Phase 9.2 execution & Phase 9.1 decision contexts.
3. Resolution of authoritative Phase 5 transaction state & Razorpay records.
4. Mapping Phase 5 TransactionState -> outcome-feedback/v1 OutcomeStatus.
5. Learning Eligibility Firewall enforcement (blocks non-terminal/unresolved states).
6. Phase 8.1 Evidence creation & persistence.
7. Phase 8.2 Reward signal evaluation.
8. Phase 8.3 Policy Memory recording (with idempotency & supersession).
9. Phase 8.4 Contextual LinUCB Model update with optimistic concurrency control.
10. Idempotent exactly-once learning effect across retries and duplicate webhooks.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import structlog
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import (
    Merchant,
    Order,
    Payment,
    DecisionExecutionRecord,
    CanonicalDecisionRecord,
    OutcomeFeedbackRecord,
    ExperimentRecord,
    ObservationRecord,
    LearningEvidenceRecord,
    AuditEvent,
)
from apps.api.core.state_machine import TransactionState
from services.commerce_service import MerchantNotFoundError
from services.runtime.schemas import DecisionEnvelope
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus,
    EvidenceLifecycleState,
)
from services.learning.features import PolicyFeatureExtractor
from services.learning.model_service import PolicyLearningModelService
from services.learning.model_errors import ConcurrentModelUpdateError
from services.reward.calculator import RewardSignalEvaluator
from services.memory.service import PolicyMemoryService
from services.outcome.schemas import (
    OUTCOME_FEEDBACK_SCHEMA_VERSION,
    OutcomeStatus,
    ProcessingState,
    OutcomeProcessRequest,
    OutcomeProcessResponse,
)
from services.outcome.errors import (
    ExecutionRecordNotFoundError,
    OutcomeTenantViolationError,
    TerminalStateConflictError,
    DownstreamLearningError,
)

logger = structlog.get_logger()


class OutcomeFeedbackService:
    """Authoritative feedback, outcome resolution, and recovery orchestrator for Phase 9.3."""

    @classmethod
    async def process_outcome(
        cls,
        db: AsyncSession,
        request: OutcomeProcessRequest
    ) -> OutcomeProcessResponse:
        """Process an execution outcome and safely advance eligible terminal states into learning."""
        t_start = time.perf_counter()
        logger.info("process_outcome_requested", execution_id=request.execution_id, merchant_id=request.merchant_id)

        # 1. Tenant Verification
        stmt_merch = select(Merchant).where(Merchant.id == request.merchant_id)
        merchant = (await db.execute(stmt_merch)).scalar_one_or_none()
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{request.merchant_id}' not found.")
        if (merchant.status or "").upper() != "ACTIVE":
            logger.warning("merchant_inactive_feedback_blocked", merchant_id=request.merchant_id)

        # 2. Idempotency Check (Existing Outcome Record)
        idemp_key = request.idempotency_key or f"idem_out_{request.merchant_id}_{request.execution_id}"
        stmt_existing = select(OutcomeFeedbackRecord).where(
            and_(
                OutcomeFeedbackRecord.merchant_id == request.merchant_id,
                OutcomeFeedbackRecord.execution_id == request.execution_id
            )
        )
        existing_outcome = (await db.execute(stmt_existing)).scalars().first()
        if existing_outcome and existing_outcome.processing_state == ProcessingState.COMPLETED.value:
            logger.info("outcome_feedback_idempotent_replay", outcome_id=existing_outcome.id)
            return cls._record_to_response(existing_outcome, is_duplicate=True)

        # 3. Load Execution Record & Verify Tenant Ownership
        stmt_exec = select(DecisionExecutionRecord).where(DecisionExecutionRecord.id == request.execution_id)
        dexec = (await db.execute(stmt_exec)).scalar_one_or_none()
        if not dexec:
            logger.error("execution_record_not_found", execution_id=request.execution_id)
            raise ExecutionRecordNotFoundError(f"Execution record '{request.execution_id}' not found.")

        if dexec.merchant_id != request.merchant_id:
            logger.error(
                "cross_tenant_outcome_blocked",
                exec_merchant=dexec.merchant_id,
                req_merchant=request.merchant_id
            )
            raise OutcomeTenantViolationError(
                f"Execution '{request.execution_id}' belongs to merchant '{dexec.merchant_id}', not '{request.merchant_id}'."
            )

        # Load Canonical Decision Context
        stmt_dec = select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == dexec.decision_id)
        decision_rec = (await db.execute(stmt_dec)).scalar_one_or_none()
        envelope = DecisionEnvelope.model_validate(decision_rec.decision_envelope_json) if decision_rec else None

        # 4. Resolve Authoritative Phase 5 Transaction State
        tx_state, payment_id, realized_rev_paise = await cls._resolve_transaction_state(db, dexec)
        logger.info("transaction_state_resolved", execution_id=request.execution_id, tx_state=tx_state.value)

        # 5. Map TransactionState -> OutcomeStatus & Terminality
        outcome_status, is_terminal, is_eligible, rejection_reasons = cls._map_state_and_eligibility(
            tx_state=tx_state,
            boundary_status=dexec.boundary_status
        )

        # Terminal State Monotonicity Invariant:
        # Once an outcome reaches terminal PAYMENT_SUCCESS, a weaker or stale event
        # (e.g. out-of-order FAILED or ORDER_CREATED) must never downgrade or regress it.
        if existing_outcome and existing_outcome.is_terminal:
            if existing_outcome.outcome_status == OutcomeStatus.PAYMENT_SUCCESS.value and outcome_status != OutcomeStatus.PAYMENT_SUCCESS:
                logger.warning(
                    "terminal_success_monotonicity_preserved",
                    existing=existing_outcome.outcome_status,
                    attempted=outcome_status.value
                )
                outcome_status = OutcomeStatus.PAYMENT_SUCCESS
                is_terminal = True
                is_eligible = True
                rejection_reasons = []

        now_utc = datetime.now(timezone.utc)
        outcome_id = existing_outcome.id if existing_outcome else f"out_{uuid.uuid4().hex[:12]}"

        # Initialize or Update Outcome Record
        if not existing_outcome:
            outcome_rec = OutcomeFeedbackRecord(
                id=outcome_id,
                merchant_id=request.merchant_id,
                opportunity_id=dexec.opportunity_id,
                decision_id=dexec.decision_id,
                execution_id=dexec.id,
                order_id=dexec.order_id,
                razorpay_order_id=dexec.razorpay_order_id,
                razorpay_payment_id=payment_id,
                feedback_version=OUTCOME_FEEDBACK_SCHEMA_VERSION,
                transaction_state=tx_state.value,
                outcome_status=outcome_status.value,
                processing_state=ProcessingState.RESOLVING.value,
                is_terminal=is_terminal,
                learning_eligible=is_eligible,
                rejection_reasons_json=rejection_reasons,
                idempotency_key=idemp_key,
                created_at=now_utc,
                updated_at=now_utc
            )
            db.add(outcome_rec)
            await db.flush()
        else:
            outcome_rec = existing_outcome
            outcome_rec.transaction_state = tx_state.value
            outcome_rec.outcome_status = outcome_status.value
            outcome_rec.is_terminal = is_terminal
            outcome_rec.learning_eligible = is_eligible
            outcome_rec.rejection_reasons_json = rejection_reasons
            outcome_rec.updated_at = now_utc

        # 6. Learning Eligibility Firewall
        # Non-terminal or ineligible states (ORDER_CREATED, UNRESOLVED, etc.) must NEVER teach the model!
        if not is_terminal or not is_eligible:
            outcome_rec.processing_state = ProcessingState.RESOLVED.value
            resp = cls._record_to_response(outcome_rec, is_duplicate=False)
            await db.commit()
            logger.info(
                "non_learning_outcome_persisted",
                outcome_id=outcome_id,
                status=outcome_status.value,
                terminal=is_terminal,
                eligible=is_eligible
            )
            return resp

        # 7. Terminal Learning Path: Progress to Learning
        # At-least-once feedback delivery with exactly-once learning effect
        evidence_id = outcome_rec.evidence_id
        memory_id = outcome_rec.memory_id
        reward_paise = outcome_rec.reward_contribution_paise

        cogs_paise = envelope.merchant_evaluation.cogs_paise if (envelope and envelope.merchant_evaluation) else 0
        policy_id = dexec.policy_id
        context_key = decision_rec.buyer_context_key if decision_rec else "bck_standard"

        if outcome_status == OutcomeStatus.PAYMENT_SUCCESS:
            obs_rev = realized_rev_paise if realized_rev_paise is not None else (dexec.authorized_amount_paise or 0)
            obs_contrib = obs_rev - cogs_paise
            outcome_type = LearningOutcomeType.PAYMENT_SUCCESS
            is_selected = True
        else:
            obs_rev = 0
            obs_contrib = 0
            outcome_type = LearningOutcomeType.PAYMENT_FAILURE
            is_selected = False

        outcome_rec.realized_revenue_paise = obs_rev
        outcome_rec.realized_cogs_paise = cogs_paise

        # Ensure runtime experiment & observation containers exist for merchant
        exp = await cls._get_or_create_runtime_experiment(db, request.merchant_id)
        obs = await cls._get_or_create_runtime_observation(
            db, exp.id, dexec.id, dexec.opportunity_id, outcome_type.value, obs_rev, obs_contrib
        )

        # 8. Phase 8.1 Evidence Ingestion
        outcome_rec.processing_state = ProcessingState.EVIDENCE_PENDING.value
        evidence_idemp_key = f"evi_out_{request.merchant_id}_{dexec.id}"
        stmt_evi = select(LearningEvidenceRecord).where(LearningEvidenceRecord.idempotency_key == evidence_idemp_key)
        existing_evi = (await db.execute(stmt_evi)).scalar_one_or_none()

        if not existing_evi:
            evi_id = f"evi_{uuid.uuid4().hex[:12]}"
            evidence = PolicyLearningEvidence(
                evidence_id=evi_id,
                evidence_version="merchant-learning/v1",
                merchant_id=request.merchant_id,
                experiment_id=exp.id,
                experiment_version="policy-experiment/v1",
                experiment_observation_id=obs.id,
                scenario_id=dexec.opportunity_id,
                policy_id=policy_id,
                policy_version="merchant-policy/v1",
                variant=VariantType.TREATMENT,
                buyer_context_key=context_key,
                buyer_intent_version="buyer-intent/v1",
                execution_id=dexec.id,
                provider_order_id=dexec.razorpay_order_id,
                verified_payment_id=payment_id,
                source=EvidenceSource.TEST_MODE_OBSERVED,
                outcome_type=outcome_type,
                sample_size=1,
                is_selected=is_selected,
                expected_revenue_paise=envelope.selected_policy.proposed_price_paise if envelope else 0,
                expected_contribution_paise=envelope.merchant_evaluation.predicted_contribution_paise if (envelope and envelope.merchant_evaluation) else 0,
                observed_revenue_paise=obs_rev,
                observed_contribution_paise=obs_contrib,
                margin_percent=envelope.merchant_evaluation.gross_margin_percent if (envelope and envelope.merchant_evaluation) else 0.0,
                guardrail_results=[],
                evidence_status=EvidenceQualityStatus.VALID,
                lifecycle_state=EvidenceLifecycleState.LEARNING_ELIGIBLE,
                learning_eligible=True,
                eligibility_reasons=["Authoritative Phase 5 transaction outcome verified."],
                aggregation_key=f"{request.merchant_id}:{context_key}:{policy_id}:merchant-policy/v1",
                idempotency_key=evidence_idemp_key,
                observed_at=now_utc
            )
            evi_rec = LearningEvidenceRecord(
                id=evi_id,
                evidence_version="merchant-learning/v1",
                merchant_id=request.merchant_id,
                experiment_id=exp.id,
                experiment_observation_id=obs.id,
                scenario_id=dexec.opportunity_id,
                policy_id=policy_id,
                policy_version="merchant-policy/v1",
                variant="TREATMENT",
                buyer_context_key=context_key,
                buyer_intent_version="buyer-intent/v1",
                execution_id=dexec.id,
                provider_order_id=dexec.razorpay_order_id,
                verified_payment_id=payment_id,
                source="TEST_MODE_OBSERVED",
                outcome_type=outcome_type.value,
                sample_size=1,
                is_selected=is_selected,
                expected_revenue_paise=evidence.expected_revenue_paise,
                expected_contribution_paise=evidence.expected_contribution_paise,
                observed_revenue_paise=obs_rev,
                observed_contribution_paise=obs_contrib,
                margin_percent=evidence.margin_percent,
                evidence_status="VALID",
                lifecycle_state="LEARNING_ELIGIBLE",
                learning_eligible=True,
                eligibility_reasons=["Authoritative Phase 5 transaction outcome verified."],
                aggregation_key=evidence.aggregation_key,
                idempotency_key=evidence_idemp_key,
                observed_at=now_utc
            )
            db.add(evi_rec)
            await db.flush()
        else:
            evidence = PolicyLearningEvidence(
                evidence_id=existing_evi.id,
                evidence_version=existing_evi.evidence_version,
                merchant_id=existing_evi.merchant_id,
                experiment_id=existing_evi.experiment_id,
                experiment_observation_id=existing_evi.experiment_observation_id,
                scenario_id=existing_evi.scenario_id,
                policy_id=existing_evi.policy_id,
                policy_version=existing_evi.policy_version,
                variant=VariantType(existing_evi.variant),
                buyer_context_key=existing_evi.buyer_context_key,
                execution_id=existing_evi.execution_id,
                provider_order_id=existing_evi.provider_order_id,
                verified_payment_id=existing_evi.verified_payment_id,
                source=EvidenceSource(existing_evi.source),
                outcome_type=LearningOutcomeType(existing_evi.outcome_type),
                sample_size=existing_evi.sample_size,
                is_selected=existing_evi.is_selected,
                expected_revenue_paise=existing_evi.expected_revenue_paise,
                expected_contribution_paise=existing_evi.expected_contribution_paise,
                observed_revenue_paise=existing_evi.observed_revenue_paise,
                observed_contribution_paise=existing_evi.observed_contribution_paise,
                margin_percent=float(existing_evi.margin_percent),
                evidence_status=EvidenceQualityStatus(existing_evi.evidence_status),
                lifecycle_state=EvidenceLifecycleState(existing_evi.lifecycle_state),
                learning_eligible=existing_evi.learning_eligible,
                aggregation_key=existing_evi.aggregation_key,
                idempotency_key=existing_evi.idempotency_key,
                observed_at=existing_evi.observed_at
            )

        evidence_id = evidence.evidence_id
        outcome_rec.evidence_id = evidence_id

        # 9. Phase 8.2 Reward Signal Evaluation
        reward = RewardSignalEvaluator.evaluate_opportunity(evidence)
        reward_paise = reward.reward_contribution_paise
        outcome_rec.reward_contribution_paise = reward_paise

        # 10. Phase 8.3 Policy Memory Recording
        outcome_rec.processing_state = ProcessingState.MEMORY_PENDING.value
        mem_schema = await PolicyMemoryService.record_observation(db, evidence, reward)
        memory_id = mem_schema.memory_id
        outcome_rec.memory_id = memory_id

        # 11. Phase 8.4 Model Update (Durable Idempotent Exactly-Once)
        outcome_rec.processing_state = ProcessingState.MODEL_PENDING.value
        x = PolicyFeatureExtractor.extract(buyer_context_key=context_key)
        try:
            was_applied, new_model_ver = await PolicyLearningModelService.apply_observation_idempotent(
                db=db,
                merchant_id=request.merchant_id,
                evidence_id=evidence.evidence_id,
                x=x,
                reward_paise=reward.reward_contribution_paise
            )
            outcome_rec.model_updated = True
        except Exception as exc:
            outcome_rec.processing_state = ProcessingState.RETRYABLE_FAILURE.value
            outcome_rec.last_error = str(exc)
            outcome_rec.retry_count = (outcome_rec.retry_count or 0) + 1
            await db.commit()
            raise DownstreamLearningError(f"Model update failed: {exc}") from exc

        # 12. Finalize Outcome Record (Strict separation: business outcome remains PAYMENT_SUCCESS, processing becomes COMPLETED)
        outcome_rec.processing_state = ProcessingState.COMPLETED.value
        outcome_rec.outcome_status = outcome_status.value

        # Persist Governance Audit Event
        audit_event = AuditEvent(
            entity_type="OUTCOME_FEEDBACK",
            entity_id=outcome_rec.id,
            actor="OUTCOME_SERVICE",
            action="OUTCOME_FEEDBACK_PROCESSED",
            payload={
                "merchant_id": request.merchant_id,
                "execution_id": dexec.id,
                "decision_id": dexec.decision_id,
                "outcome_status": outcome_rec.outcome_status,
                "transaction_state": tx_state.value,
                "learning_eligible": True,
                "evidence_id": evidence_id,
                "memory_id": memory_id,
                "reward_paise": reward_paise,
                "model_updated": True
            }
        )
        db.add(audit_event)
        resp = cls._record_to_response(outcome_rec, is_duplicate=False)
        await db.commit()

        logger.info(
            "outcome_feedback_completed",
            outcome_id=outcome_rec.id,
            status=outcome_rec.outcome_status,
            reward_paise=reward_paise
        )

        return resp

    @classmethod
    async def get_outcome(
        cls,
        db: AsyncSession,
        outcome_id: str,
        merchant_id: str
    ) -> OutcomeProcessResponse:
        """Retrieve authoritative outcome record by primary ID with strict tenant scoping."""
        stmt = select(OutcomeFeedbackRecord).where(
            and_(
                OutcomeFeedbackRecord.id == outcome_id,
                OutcomeFeedbackRecord.merchant_id == merchant_id
            )
        )
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if not rec:
            raise ExecutionRecordNotFoundError(f"Outcome record '{outcome_id}' not found.")
        return cls._record_to_response(rec, is_duplicate=False)

    @classmethod
    async def get_outcome_by_execution(
        cls,
        db: AsyncSession,
        execution_id: str,
        merchant_id: str
    ) -> OutcomeProcessResponse:
        """Retrieve authoritative outcome record by execution ID with strict tenant scoping."""
        stmt = select(OutcomeFeedbackRecord).where(
            and_(
                OutcomeFeedbackRecord.execution_id == execution_id,
                OutcomeFeedbackRecord.merchant_id == merchant_id
            )
        )
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if not rec:
            raise ExecutionRecordNotFoundError(f"Outcome record for execution '{execution_id}' not found.")
        return cls._record_to_response(rec, is_duplicate=False)

    @classmethod
    async def process_webhook_outcome(
        cls,
        db: AsyncSession,
        order_id: str,
        event_type: str,
        payment_id: Optional[str] = None
    ) -> Optional[OutcomeProcessResponse]:
        """Hook automatically invoked by Phase 5 WebhookService to progress feedback upon webhook arrival."""
        stmt = select(DecisionExecutionRecord).where(
            or_(
                DecisionExecutionRecord.order_id == order_id,
                DecisionExecutionRecord.razorpay_order_id == order_id
            )
        )
        dexec = (await db.execute(stmt)).scalar_one_or_none()
        if not dexec:
            return None

        req = OutcomeProcessRequest(
            merchant_id=dexec.merchant_id,
            execution_id=dexec.id,
            idempotency_key=f"idem_wh_out_{dexec.merchant_id}_{dexec.id}"
        )
        return await cls.process_outcome(db, req)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @classmethod
    async def _resolve_transaction_state(
        cls,
        db: AsyncSession,
        dexec: DecisionExecutionRecord
    ) -> Tuple[TransactionState, Optional[str], Optional[int]]:
        """Resolve authoritative Phase 5 transaction state, payment ID, and realized amount."""
        if not dexec.order_id:
            if dexec.boundary_status != "EXECUTION_COMPLETED":
                return TransactionState.FAILED, None, 0
            return TransactionState.CREATION_PENDING, None, None

        stmt_order = select(Order).where(Order.id == dexec.order_id)
        order = (await db.execute(stmt_order)).scalar_one_or_none()
        if not order:
            return TransactionState.UNCERTAIN, None, None

        order_status = TransactionState(order.status)
        stmt_payments = select(Payment).where(Payment.order_id == order.id)
        payments = (await db.execute(stmt_payments)).scalars().all()

        captured = next((p for p in payments if p.status == "captured"), None)
        failed = next((p for p in payments if p.status == "failed"), None)

        if captured:
            return TransactionState.PAID, captured.id, captured.amount_paise
        elif order_status in (TransactionState.PAID, TransactionState.FINALIZED):
            return TransactionState.PAID, None, order.amount_paise
        elif failed:
            return TransactionState.FAILED, failed.id, 0
        elif order_status in (TransactionState.FAILED, TransactionState.CANCELLED):
            return order_status, None, 0
        else:
            return order_status, None, None

    @classmethod
    def _map_state_and_eligibility(
        cls,
        tx_state: TransactionState,
        boundary_status: str
    ) -> Tuple[OutcomeStatus, bool, bool, List[str]]:
        """Map authoritative TransactionState to OutcomeStatus and derive learning eligibility."""
        reasons = []

        if boundary_status != "EXECUTION_COMPLETED":
            return (
                OutcomeStatus.EXECUTION_FAILED,
                True,
                True,  # Eligible as non-purchase / guardrail failure observation (reward = 0)
                [f"BOUNDARY_REJECTED: Execution status was '{boundary_status}'."]
            )

        if tx_state in (TransactionState.PAID, TransactionState.FINALIZED):
            return OutcomeStatus.PAYMENT_SUCCESS, True, True, []

        elif tx_state == TransactionState.FAILED:
            return OutcomeStatus.PAYMENT_FAILED, True, True, []

        elif tx_state == TransactionState.CANCELLED:
            return OutcomeStatus.PAYMENT_CANCELLED, True, True, []

        elif tx_state == TransactionState.ORDER_CREATED:
            reasons.append("ORDER_CREATED is non-terminal: payment has not been captured.")
            return OutcomeStatus.ORDER_CREATED, False, False, reasons

        elif tx_state in (TransactionState.CREATION_PENDING, TransactionState.PAYMENT_PENDING, TransactionState.AUTHORIZED):
            reasons.append(f"Transaction state '{tx_state.value}' is non-terminal.")
            return OutcomeStatus.PENDING, False, False, reasons

        elif tx_state == TransactionState.UNCERTAIN:
            reasons.append("UNCERTAIN transaction state requires reconciliation.")
            return OutcomeStatus.UNRESOLVED, False, False, reasons

        reasons.append(f"Unmapped transaction state: {tx_state.value}")
        return OutcomeStatus.UNRESOLVED, False, False, reasons

    @classmethod
    async def _get_or_create_runtime_experiment(cls, db: AsyncSession, merchant_id: str) -> ExperimentRecord:
        """Get or create the canonical operational runtime experiment container for a merchant tenant."""
        exp_id = f"exp_runtime_{merchant_id}"
        stmt = select(ExperimentRecord).where(ExperimentRecord.id == exp_id)
        exp = (await db.execute(stmt)).scalar_one_or_none()
        if not exp:
            exp = ExperimentRecord(
                id=exp_id,
                merchant_id=merchant_id,
                name="Operational Decision Runtime",
                control_policy_id="cand_baseline",
                treatment_policy_id="cand_active",
                control_proposal_snapshot={"merchant_id": merchant_id},
                treatment_proposal_snapshot={"merchant_id": merchant_id},
                hypothesis={
                    "population_description": "Operational Runtime",
                    "control_description": "Baseline",
                    "treatment_description": "Learned Offer",
                    "expected_direction": "HIGHER",
                    "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
                    "rationale": "Closed-loop feedback runtime"
                },
                status="RUNNING"
            )
            db.add(exp)
            await db.flush()
        return exp

    @classmethod
    async def _get_or_create_runtime_observation(
        cls,
        db: AsyncSession,
        exp_id: str,
        execution_id: str,
        scenario_id: str,
        outcome_type: str,
        revenue_paise: int,
        contribution_paise: int
    ) -> ObservationRecord:
        """Get or create the operational runtime observation record for an execution."""
        obs_id = f"obs_{execution_id}"
        stmt = select(ObservationRecord).where(ObservationRecord.id == obs_id)
        obs = (await db.execute(stmt)).scalar_one_or_none()
        if not obs:
            obs = ObservationRecord(
                id=obs_id,
                experiment_id=exp_id,
                scenario_id=scenario_id,
                variant="TREATMENT",
                outcome_type="TEST_MODE_OBSERVED",
                is_selected=(outcome_type == "PAYMENT_SUCCESS"),
                execution_id=None,
                order_id=None,
                payment_outcome="CAPTURED" if outcome_type == "PAYMENT_SUCCESS" else "FAILED",
                revenue_paise=revenue_paise,
                contribution_paise=contribution_paise,
                margin_percent=0.0,
                guardrail_violations=[],
                idempotency_key=f"obs_idem_{execution_id}"
            )
            db.add(obs)
            await db.flush()
        return obs

    @classmethod
    def _record_to_response(
        cls,
        rec: OutcomeFeedbackRecord,
        is_duplicate: bool,
        processed_at: Optional[datetime] = None
    ) -> OutcomeProcessResponse:
        """Convert database OutcomeFeedbackRecord to clean customer-safe OutcomeProcessResponse."""
        effective_processed_at = processed_at or datetime.now(timezone.utc)
        return OutcomeProcessResponse(
            outcome_id=rec.id,
            merchant_id=rec.merchant_id,
            opportunity_id=rec.opportunity_id,
            decision_id=rec.decision_id,
            execution_id=rec.execution_id,
            order_id=rec.order_id,
            razorpay_order_id=rec.razorpay_order_id,
            razorpay_payment_id=rec.razorpay_payment_id,
            transaction_state=rec.transaction_state,
            outcome_status=OutcomeStatus(rec.outcome_status),
            processing_state=ProcessingState(rec.processing_state),
            is_terminal=rec.is_terminal,
            learning_eligible=rec.learning_eligible,
            evidence_id=rec.evidence_id,
            memory_id=rec.memory_id,
            realized_revenue_paise=rec.realized_revenue_paise,
            reward_contribution_paise=rec.reward_contribution_paise,
            rejection_reasons=rec.rejection_reasons_json or [],
            is_duplicate=is_duplicate,
            processed_at=effective_processed_at,
            feedback_version=OUTCOME_FEEDBACK_SCHEMA_VERSION
        )
