"""Authoritative State Observer for Phase 11.1 Canonical Benchmark Harness.

Collects authoritative state from production database tables and runtime entities
under strict information-hygiene rules:
- Zero leakage of raw secrets, credentials, or provider auth headers.
- Zero leakage of confidential internal unit economics (COGS, margins).
- Gathers clean typed facts needed for assertion evaluation.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import (
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    PolicyMemoryRecord,
    PolicyLearningModelState,
    MerchantActivePolicy,
    AuditEvent,
)
from services.benchmark.schemas import ObservedStateSnapshot


class BenchmarkObserver:
    """Extracts authoritative system observations without compromising information hygiene."""

    @classmethod
    async def capture(
        cls,
        db: AsyncSession,
        merchant_id: str,
        opportunity_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
        is_duplicate_execution: bool = False,
        is_duplicate_outcome: bool = False,
        promotion_status: Optional[str] = None,
        promotion_failure_code: Optional[str] = None,
        cross_tenant_rejected: Optional[bool] = None,
        stale_state_rejected: Optional[bool] = None,
    ) -> ObservedStateSnapshot:
        """Query authoritative records and construct a sanitized ObservedStateSnapshot."""
        snapshot = ObservedStateSnapshot(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            is_duplicate_execution=is_duplicate_execution,
            is_duplicate_outcome=is_duplicate_outcome,
            promotion_status=promotion_status,
            promotion_failure_code=promotion_failure_code,
            cross_tenant_rejected=cross_tenant_rejected,
            stale_state_rejected=stale_state_rejected,
        )

        # 1. Decision State (Phase 9.1)
        if decision_id:
            stmt_dec = select(CanonicalDecisionRecord).where(
                and_(
                    CanonicalDecisionRecord.id == decision_id,
                    CanonicalDecisionRecord.merchant_id == merchant_id,
                )
            )
            dec_rec = (await db.execute(stmt_dec)).scalar_one_or_none()
            if dec_rec:
                snapshot.decision_id = dec_rec.id
                snapshot.opportunity_id = dec_rec.opportunity_id
                snapshot.decision_mode = dec_rec.decision_mode
                snapshot.selected_policy_id = dec_rec.selected_policy_id
                snapshot.selected_strategy = dec_rec.selected_strategy_type
                envelope = dec_rec.decision_envelope_json or {}
                snapshot.execution_authorized_9_1 = bool(envelope.get("execution_authorized", False))
                buyer_offer = envelope.get("buyer_offer") or {}
                snapshot.offered_price_paise = buyer_offer.get("offered_price_paise")

        # 2. Execution Boundary State (Phase 9.2)
        if execution_id:
            stmt_exec = select(DecisionExecutionRecord).where(
                and_(
                    DecisionExecutionRecord.id == execution_id,
                    DecisionExecutionRecord.merchant_id == merchant_id,
                )
            )
            exec_rec = (await db.execute(stmt_exec)).scalar_one_or_none()
            if exec_rec:
                snapshot.execution_id = exec_rec.id
                snapshot.boundary_status = exec_rec.boundary_status
                snapshot.authorized_amount_paise = exec_rec.authorized_amount_paise
                snapshot.order_id = exec_rec.order_id

        # 3. Outcome Feedback State (Phase 9.3)
        if outcome_id or execution_id:
            query = select(OutcomeFeedbackRecord).where(
                OutcomeFeedbackRecord.merchant_id == merchant_id
            )
            if outcome_id:
                query = query.where(OutcomeFeedbackRecord.id == outcome_id)
            elif execution_id:
                query = query.where(OutcomeFeedbackRecord.execution_id == execution_id)

            outcome_rec = (await db.execute(query)).scalars().first()
            if outcome_rec:
                snapshot.outcome_id = outcome_rec.id
                snapshot.outcome_status = outcome_rec.outcome_status
                snapshot.is_terminal = outcome_rec.is_terminal
                snapshot.learning_eligible = outcome_rec.learning_eligible
                snapshot.reward_contribution_paise = outcome_rec.reward_contribution_paise
                snapshot.evidence_id = outcome_rec.evidence_id
                snapshot.memory_id = outcome_rec.memory_id

        # 4. Active Policy State (Phase 8.8)
        stmt_act = select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == merchant_id)
        act_rec = (await db.execute(stmt_act)).scalar_one_or_none()
        if act_rec:
            snapshot.active_policy_id = act_rec.policy_id

        # 5. Bandit Model Observation Count (Phase 8.4)
        stmt_model = select(PolicyLearningModelState).where(
            PolicyLearningModelState.merchant_id == merchant_id
        )
        model_rec = (await db.execute(stmt_model)).scalar_one_or_none()
        if model_rec:
            snapshot.model_observation_count = model_rec.observation_count

        # 6. Policy Memory Count & Contribution Aggregate (Phase 8.3)
        stmt_mem_count = select(func.count(PolicyMemoryRecord.id)).where(
            PolicyMemoryRecord.merchant_id == merchant_id
        )
        snapshot.memory_count = (await db.execute(stmt_mem_count)).scalar() or 0

        stmt_mem_sum = select(
            func.coalesce(func.sum(PolicyMemoryRecord.reward_contribution_paise), 0)
        ).where(PolicyMemoryRecord.merchant_id == merchant_id)
        snapshot.total_observed_contribution_paise = (await db.execute(stmt_mem_sum)).scalar() or 0

        # 7. Audit Events
        stmt_audit = select(AuditEvent.id).where(AuditEvent.merchant_id == merchant_id).limit(20)
        snapshot.audit_event_ids = list((await db.execute(stmt_audit)).scalars().all())

        return snapshot
