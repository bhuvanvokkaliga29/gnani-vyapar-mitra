"""Authoritative service implementation for Phase 8.3 Merchant Policy Memory layer."""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from domain.models import PolicyMemoryRecord, LearningEvidenceRecord
from services.learning.schemas import PolicyLearningEvidence, EvidenceSource, LearningOutcomeType
from services.reward.schemas import PolicyOpportunityReward, RewardState
from services.reward.calculator import RewardSignalEvaluator
from services.memory.schemas import (
    PolicyMemoryRecordSchema,
    HistoricalObservationFilter,
    HistoricalObservationList,
    HistoricalPolicySummary
)
from services.memory.errors import (
    MemoryError,
    DuplicateMemoryRecordError,
    MemoryTenantViolationError,
    MemoryProvenanceError,
    MemoryImmutableError
)


class PolicyMemoryService:
    """Provides append-only persistence and deterministic historical retrieval for policy memory."""

    @classmethod
    async def record_observation(
        cls,
        db: AsyncSession,
        evidence: PolicyLearningEvidence,
        reward: Optional[PolicyOpportunityReward] = None,
        correction_reason: Optional[str] = None,
        reconciliation_ref: Optional[str] = None
    ) -> PolicyMemoryRecordSchema:
        """Persist an authoritative learning observation and its reward into immutable historical memory.
        
        Idempotent: Replayed evidence with matching idempotency key returns the existing record.
        Reconciled / Superseding: If a previous record exists for (merchant_id, opportunity_id),
        the previous record is linked and marked is_current=False, while the new record becomes is_current=True.
        """
        # 1. Derive reward if not supplied
        if reward is None:
            reward = RewardSignalEvaluator.evaluate_opportunity(evidence)

        # 2. Strict Tenant Scoping Check
        if evidence.merchant_id != reward.merchant_id:
            raise MemoryTenantViolationError(
                f"Cross-tenant memory record rejected: evidence '{evidence.merchant_id}' != reward '{reward.merchant_id}'."
            )

        # 3. Deterministic Deduplication / Idempotency
        idempotency_key = f"mem_{evidence.evidence_id}"
        stmt_existing = select(PolicyMemoryRecord).where(PolicyMemoryRecord.idempotency_key == idempotency_key)
        res_existing = await db.execute(stmt_existing)
        existing_record = res_existing.scalar_one_or_none()
        if existing_record:
            # Enforce tenant isolation on idempotent return
            if existing_record.merchant_id != evidence.merchant_id:
                raise MemoryTenantViolationError("Tenant collision detected on idempotent memory key.")
            return cls._to_schema(existing_record)

        # 4. Handle Supersession / Reconciliation Lineage
        record_id = f"mem_{uuid.uuid4().hex[:12]}"
        stmt_prev = select(PolicyMemoryRecord).where(
            and_(
                PolicyMemoryRecord.merchant_id == evidence.merchant_id,
                PolicyMemoryRecord.opportunity_id == reward.opportunity_id,
                PolicyMemoryRecord.is_current == True
            )
        )
        res_prev = await db.execute(stmt_prev)
        prev_record = res_prev.scalar_one_or_none()
        
        supersedes_id = None
        if prev_record:
            # Link previous record and mark non-current without destroying its history
            prev_record.is_current = False
            prev_record.superseded_by = record_id
            supersedes_id = prev_record.id

        # 5. Construct Immutable Database Model
        db_record = PolicyMemoryRecord(
            id=record_id,
            memory_version="merchant-memory/v1",
            merchant_id=evidence.merchant_id,
            opportunity_id=reward.opportunity_id,
            buyer_context_key=evidence.buyer_context_key,
            scenario_id=evidence.scenario_id,
            policy_id=evidence.policy_id,
            policy_version=evidence.policy_version,
            experiment_id=evidence.experiment_id,
            experiment_version=evidence.experiment_version,
            variant=evidence.variant.value,
            evidence_id=evidence.evidence_id,
            evidence_source=evidence.source.value,
            outcome_type=evidence.outcome_type.value,
            learning_eligible=evidence.learning_eligible,
            reward_id=reward.reward_id,
            reward_version=reward.reward_version,
            formula_version=reward.formula_version,
            reward_state=reward.reward_state.value,
            is_admissible=reward.is_admissible,
            is_safety_violation=reward.is_safety_violation,
            realized_revenue_paise=reward.realized_revenue_paise,
            realized_cogs_paise=reward.realized_cogs_paise,
            realized_discount_paise=reward.realized_discount_paise,
            reward_contribution_paise=reward.reward_contribution_paise,
            margin_percent=reward.margin_percent,
            is_current=True,
            superseded_by=None,
            supersedes=supersedes_id,
            correction_reason=correction_reason,
            reconciliation_ref=reconciliation_ref,
            idempotency_key=idempotency_key,
            observed_at=evidence.observed_at
        )

        db.add(db_record)
        await db.commit()
        await db.refresh(db_record)
        return cls._to_schema(db_record)

    @classmethod
    async def get_observation(
        cls,
        db: AsyncSession,
        merchant_id: str,
        memory_id: str
    ) -> Optional[PolicyMemoryRecordSchema]:
        """Fetch an individual historical observation, strictly enforcing merchant tenant isolation."""
        stmt = select(PolicyMemoryRecord).where(PolicyMemoryRecord.id == memory_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return None

        if record.merchant_id != merchant_id:
            raise MemoryTenantViolationError(
                f"Merchant '{merchant_id}' unauthorized to view memory of '{record.merchant_id}'."
            )
        return cls._to_schema(record)

    @classmethod
    async def query_history(
        cls,
        db: AsyncSession,
        filter_params: HistoricalObservationFilter
    ) -> HistoricalObservationList:
        """Deterministically query and retrieve historical observations with stable ordering and pagination."""
        conditions = [PolicyMemoryRecord.merchant_id == filter_params.merchant_id]

        if filter_params.policy_id:
            conditions.append(PolicyMemoryRecord.policy_id == filter_params.policy_id)
        if filter_params.policy_version:
            conditions.append(PolicyMemoryRecord.policy_version == filter_params.policy_version)
        if filter_params.buyer_context_key:
            conditions.append(PolicyMemoryRecord.buyer_context_key == filter_params.buyer_context_key)
        if filter_params.experiment_id:
            conditions.append(PolicyMemoryRecord.experiment_id == filter_params.experiment_id)
        if filter_params.variant:
            conditions.append(PolicyMemoryRecord.variant == filter_params.variant.value)
        if filter_params.evidence_source:
            conditions.append(PolicyMemoryRecord.evidence_source == filter_params.evidence_source.value)
        if filter_params.learning_eligible_only is not None:
            conditions.append(PolicyMemoryRecord.learning_eligible == filter_params.learning_eligible_only)
        if filter_params.is_admissible_only is not None:
            conditions.append(PolicyMemoryRecord.is_admissible == filter_params.is_admissible_only)
        if filter_params.is_current_only is not None:
            conditions.append(PolicyMemoryRecord.is_current == filter_params.is_current_only)
        if filter_params.start_time:
            conditions.append(PolicyMemoryRecord.observed_at >= filter_params.start_time)
        if filter_params.end_time:
            conditions.append(PolicyMemoryRecord.observed_at <= filter_params.end_time)

        # 1. Total Count Query
        count_stmt = select(func.count(PolicyMemoryRecord.id)).where(and_(*conditions))
        count_res = await db.execute(count_stmt)
        total_count = count_res.scalar_one()

        # 2. Data Query with Deterministic Ordering (observed_at DESC, id ASC)
        data_stmt = (
            select(PolicyMemoryRecord)
            .where(and_(*conditions))
            .order_by(PolicyMemoryRecord.observed_at.desc(), PolicyMemoryRecord.id.asc())
            .limit(filter_params.limit)
            .offset(filter_params.offset)
        )
        data_res = await db.execute(data_stmt)
        records = data_res.scalars().all()

        return HistoricalObservationList(
            total_count=total_count,
            limit=filter_params.limit,
            offset=filter_params.offset,
            items=[cls._to_schema(r) for r in records]
        )

    @classmethod
    async def get_policy_summary(
        cls,
        db: AsyncSession,
        merchant_id: str,
        policy_id: str,
        buyer_context_key: Optional[str] = None,
        policy_version: Optional[str] = None,
        is_current_only: bool = True
    ) -> HistoricalPolicySummary:
        """Compute factual historical summary metrics for a policy under a context or merchant-wide.
        
        Strict Invariant: Returns facts and aggregates ONLY. No recommendations, no rankings, no decisions.
        Default View: is_current_only=True evaluates authoritative current state and prevents double-counting.
        """
        conditions = [
            PolicyMemoryRecord.merchant_id == merchant_id,
            PolicyMemoryRecord.policy_id == policy_id
        ]
        if is_current_only:
            conditions.append(PolicyMemoryRecord.is_current == True)
        if buyer_context_key:
            conditions.append(PolicyMemoryRecord.buyer_context_key == buyer_context_key)
        if policy_version:
            conditions.append(PolicyMemoryRecord.policy_version == policy_version)

        stmt = select(PolicyMemoryRecord).where(and_(*conditions))
        res = await db.execute(stmt)
        records = res.scalars().all()

        view_name = "CURRENT_EFFECTIVE" if is_current_only else "RAW_HISTORICAL"
        if not records:
            return HistoricalPolicySummary(
                merchant_id=merchant_id,
                policy_id=policy_id,
                policy_version=policy_version,
                buyer_context_key=buyer_context_key,
                evaluation_view=view_name
            )

        total_opps = len(records)
        admissible_records = [r for r in records if r.is_admissible]
        eligible_opps = len(admissible_records)
        ineligible_opps = total_opps - eligible_opps
        guardrail_violations = sum(1 for r in records if r.is_safety_violation or r.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION.value)
        is_policy_admissible = (guardrail_violations == 0)

        converted_payments = sum(
            1 for r in admissible_records
            if r.reward_state == RewardState.REWARD_ELIGIBLE.value and r.reward_contribution_paise > 0
        )
        conversion_rate = round(converted_payments / eligible_opps, 4) if eligible_opps > 0 else 0.0

        order_created_count = sum(1 for r in admissible_records if r.realized_revenue_paise > 0)
        total_rev = sum(r.realized_revenue_paise for r in admissible_records)
        total_cogs = sum(r.realized_cogs_paise for r in admissible_records)
        total_contrib = sum(r.reward_contribution_paise for r in admissible_records)

        if eligible_opps > 0:
            c_dec = Decimal(total_contrib)
            o_dec = Decimal(eligible_opps)
            contrib_per_shopper_dec = float((c_dec / o_dec).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
            contrib_per_shopper_int = int((c_dec / o_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        else:
            contrib_per_shopper_dec = 0.0
            contrib_per_shopper_int = 0

        if total_rev > 0:
            rev_d = Decimal(total_rev)
            cogs_d = Decimal(total_cogs)
            avg_margin_pct = float((((rev_d - cogs_d) / rev_d) * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            avg_margin_pct = 0.0

        all_dates = [r.observed_at for r in records]
        earliest_observed = min(all_dates) if all_dates else None
        latest_observed = max(all_dates) if all_dates else None

        return HistoricalPolicySummary(
            merchant_id=merchant_id,
            policy_id=policy_id,
            policy_version=policy_version,
            buyer_context_key=buyer_context_key,
            evaluation_view=view_name,
            total_opportunities=total_opps,
            eligible_opportunities=eligible_opps,
            ineligible_opportunities=ineligible_opps,
            guardrail_violations=guardrail_violations,
            is_policy_admissible=is_policy_admissible,
            order_created_count=order_created_count,
            converted_payments=converted_payments,
            conversion_rate=conversion_rate,
            total_realized_revenue_paise=total_rev,
            total_realized_cogs_paise=total_cogs,
            total_contribution_paise=total_contrib,
            contribution_per_shopper_paise=contrib_per_shopper_int,
            contribution_per_shopper_decimal=contrib_per_shopper_dec,
            average_margin_percent=avg_margin_pct,
            earliest_observed_at=earliest_observed,
            latest_observed_at=latest_observed
        )

    @classmethod
    def _to_schema(cls, record: PolicyMemoryRecord) -> PolicyMemoryRecordSchema:
        """Convert SQLAlchemy database record into Pydantic v2 schema."""
        from services.experiments.schemas import VariantType
        from services.learning.schemas import EvidenceSource, LearningOutcomeType
        from services.reward.schemas import RewardState

        return PolicyMemoryRecordSchema(
            memory_id=record.id,
            memory_version=record.memory_version,
            merchant_id=record.merchant_id,
            opportunity_id=record.opportunity_id,
            buyer_context_key=record.buyer_context_key,
            scenario_id=record.scenario_id,
            policy_id=record.policy_id,
            policy_version=record.policy_version,
            experiment_id=record.experiment_id,
            experiment_version=record.experiment_version,
            variant=VariantType(record.variant),
            evidence_id=record.evidence_id,
            evidence_source=EvidenceSource(record.evidence_source),
            outcome_type=LearningOutcomeType(record.outcome_type),
            learning_eligible=record.learning_eligible,
            reward_id=record.reward_id,
            reward_version=record.reward_version,
            formula_version=record.formula_version,
            reward_state=RewardState(record.reward_state),
            is_admissible=record.is_admissible,
            is_safety_violation=record.is_safety_violation,
            realized_revenue_paise=record.realized_revenue_paise,
            realized_cogs_paise=record.realized_cogs_paise,
            realized_discount_paise=record.realized_discount_paise,
            reward_contribution_paise=record.reward_contribution_paise,
            margin_percent=float(record.margin_percent),
            is_current=record.is_current,
            superseded_by=record.superseded_by,
            supersedes=record.supersedes,
            correction_reason=record.correction_reason,
            reconciliation_ref=record.reconciliation_ref,
            idempotency_key=record.idempotency_key,
            observed_at=record.observed_at,
            persisted_at=record.persisted_at
        )
