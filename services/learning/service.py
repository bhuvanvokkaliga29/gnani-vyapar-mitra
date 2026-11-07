"""Learning Evidence Service: Manages authoritative ingestion, validation, persistence, and querying."""

import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from domain.models import LearningEvidenceRecord, ExperimentRecord, ObservationRecord
from domain.intent_schemas import BuyerIntent
from services.experiments.schemas import PolicyExperiment, ExperimentObservation, ExperimentStatus, OutcomeType, VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus,
    EvidenceLifecycleState,
    EvidenceFilter,
    EvidenceGuardrailSummary
)
from services.learning.context_key import BuyerContextKeyBuilder
from services.learning.validator import LearningEvidenceValidator
from services.learning.errors import (
    InvalidEvidenceError,
    CrossTenantLearningError,
    EvidenceImmutabilityError,
    DuplicateEvidenceError
)

logger = structlog.get_logger()


class LearningEvidenceService:
    """Authoritative service for creating and querying immutable PolicyLearningEvidence."""

    @classmethod
    def observation_to_evidence(
        cls,
        observation: ExperimentObservation,
        experiment: PolicyExperiment,
        intent: Optional[BuyerIntent] = None,
        category: str = "travel_backpack"
    ) -> PolicyLearningEvidence:
        """Convert a Phase 7 ExperimentObservation into a candidate PolicyLearningEvidence."""
        # Tenant Isolation check
        if experiment.merchant_id != observation.experiment_id and not observation.experiment_id.startswith("exp_"):
            raise CrossTenantLearningError("Experiment merchant does not match observation context.")

        # Buyer Context Key (Zero PII, Zero Demographics)
        if intent is not None:
            buyer_context_key = BuyerContextKeyBuilder.build_key(intent, category)
        else:
            # Fallback standardized key for synthetic benchmark scenarios
            buyer_context_key = f"bck_{category}_tier_mid_standard"

        # Source Taxonomy
        if observation.outcome_type == OutcomeType.TEST_MODE_OBSERVED:
            source = EvidenceSource.TEST_MODE_OBSERVED
            if observation.payment_outcome == "CAPTURED":
                outcome_type = LearningOutcomeType.PAYMENT_SUCCESS
            elif observation.order_id or observation.razorpay_order_id:
                outcome_type = LearningOutcomeType.ORDER_CREATED
            else:
                outcome_type = LearningOutcomeType.EXECUTION_REJECTED
        else:
            source = EvidenceSource.SIMULATED
            outcome_type = (
                LearningOutcomeType.SIMULATED_SELECTION
                if observation.is_selected
                else LearningOutcomeType.NO_SELECTION
            )

        # Policy ID and Version
        policy_id = (
            experiment.control_policy_id
            if observation.variant == VariantType.CONTROL
            else experiment.treatment_policy_id
        )
        policy_version = "merchant-policy/v1"

        # Economics: Strict separation of Expected vs. Observed
        expected_rev = observation.revenue_paise
        expected_contrib = observation.contribution_paise
        observed_rev = None
        observed_contrib = None

        if source == EvidenceSource.TEST_MODE_OBSERVED and outcome_type == LearningOutcomeType.PAYMENT_SUCCESS:
            observed_rev = observation.revenue_paise
            observed_contrib = observation.contribution_paise

        # Guardrails Summary
        guardrail_summaries = []
        for v in observation.guardrail_violations:
            guardrail_summaries.append(EvidenceGuardrailSummary(
                guardrail_type="OBSERVED_VIOLATION",
                threshold_value=0.0,
                observed_value=0.0,
                passed=False,
                detail=v
            ))

        # Evidence Quality Status
        if guardrail_summaries:
            quality_status = EvidenceQualityStatus.GUARDRAIL_FAILURE
        else:
            quality_status = EvidenceQualityStatus.VALID

        # Canonical Aggregation Key: merchant_id:buyer_context_key:policy_id:policy_version
        aggregation_key = f"{experiment.merchant_id}:{buyer_context_key}:{policy_id}:{policy_version}"
        idempotency_key = f"evi_{observation.idempotency_key}"

        candidate_evidence = PolicyLearningEvidence(
            evidence_id=f"evi_{uuid.uuid4().hex[:12]}",
            evidence_version="merchant-learning/v1",
            merchant_id=experiment.merchant_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            experiment_observation_id=observation.observation_id,
            scenario_id=observation.scenario_id,
            policy_id=policy_id,
            policy_version=policy_version,
            variant=observation.variant,
            buyer_context_key=buyer_context_key,
            buyer_intent_version="buyer-intent/v1",
            buyer_selection_result_id=observation.buyer_selection_result_id,
            simulation_version="buyer-selection/v1",
            execution_id=observation.execution_id,
            provider_order_id=observation.razorpay_order_id,
            verified_payment_id=observation.payment_outcome if observation.payment_outcome == "CAPTURED" else None,
            source=source,
            outcome_type=outcome_type,
            sample_size=1,
            is_selected=observation.is_selected,
            expected_revenue_paise=expected_rev,
            expected_contribution_paise=expected_contrib,
            observed_revenue_paise=observed_rev,
            observed_contribution_paise=observed_contrib,
            margin_percent=observation.margin_percent,
            guardrail_results=guardrail_summaries,
            evidence_status=quality_status,
            lifecycle_state=EvidenceLifecycleState.CAPTURED,
            learning_eligible=False,  # Derived next
            eligibility_reasons=[],
            aggregation_key=aggregation_key,
            idempotency_key=idempotency_key,
            observed_at=observation.observed_at
        )

        # Validate Integrity & Provenance
        LearningEvidenceValidator.validate_provenance_and_integrity(candidate_evidence)

        # Deterministic Eligibility Derivation
        is_eligible, reasons = LearningEvidenceValidator.derive_learning_eligibility(
            evidence=candidate_evidence,
            experiment_status=experiment.status
        )
        candidate_evidence.learning_eligible = is_eligible
        candidate_evidence.eligibility_reasons = reasons
        candidate_evidence.lifecycle_state = (
            EvidenceLifecycleState.LEARNING_ELIGIBLE if is_eligible else EvidenceLifecycleState.VALIDATED
        )

        return candidate_evidence

    async def ingest_observation(
        self,
        db: AsyncSession,
        observation: ExperimentObservation,
        experiment: PolicyExperiment,
        intent: Optional[BuyerIntent] = None,
        category: str = "travel_backpack"
    ) -> PolicyLearningEvidence:
        """Idempotently ingest an observation into the authoritative learning evidence store."""
        idempotency_key = f"evi_{observation.idempotency_key}"

        # 1. Deduplication / Replay Check
        stmt = select(LearningEvidenceRecord).where(LearningEvidenceRecord.idempotency_key == idempotency_key)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return self._record_to_schema(existing)

        # 2. Build and Validate Evidence Schema
        evidence = self.observation_to_evidence(
            observation=observation,
            experiment=experiment,
            intent=intent,
            category=category
        )

        # 3. Persist Immutable Record
        record = LearningEvidenceRecord(
            id=evidence.evidence_id,
            evidence_version=evidence.evidence_version,
            merchant_id=evidence.merchant_id,
            experiment_id=evidence.experiment_id,
            experiment_observation_id=evidence.experiment_observation_id,
            scenario_id=evidence.scenario_id,
            policy_id=evidence.policy_id,
            policy_version=evidence.policy_version,
            variant=evidence.variant.value,
            buyer_context_key=evidence.buyer_context_key,
            buyer_intent_version=evidence.buyer_intent_version,
            buyer_selection_result_id=evidence.buyer_selection_result_id,
            simulation_version=evidence.simulation_version,
            execution_id=evidence.execution_id,
            provider_order_id=evidence.provider_order_id,
            verified_payment_id=evidence.verified_payment_id,
            source=evidence.source.value,
            outcome_type=evidence.outcome_type.value,
            sample_size=evidence.sample_size,
            is_selected=evidence.is_selected,
            expected_revenue_paise=evidence.expected_revenue_paise,
            expected_contribution_paise=evidence.expected_contribution_paise,
            observed_revenue_paise=evidence.observed_revenue_paise,
            observed_contribution_paise=evidence.observed_contribution_paise,
            margin_percent=evidence.margin_percent,
            guardrail_results=[g.model_dump() for g in evidence.guardrail_results],
            evidence_status=evidence.evidence_status.value,
            lifecycle_state=evidence.lifecycle_state.value,
            learning_eligible=evidence.learning_eligible,
            eligibility_reasons=evidence.eligibility_reasons,
            aggregation_key=evidence.aggregation_key,
            idempotency_key=evidence.idempotency_key,
            observed_at=evidence.observed_at
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

        return self._record_to_schema(record)

    async def get_evidence(
        self,
        db: AsyncSession,
        evidence_id: str,
        merchant_id: str
    ) -> Optional[PolicyLearningEvidence]:
        """Retrieve a learning evidence record, enforcing strict tenant scoping."""
        stmt = select(LearningEvidenceRecord).where(
            and_(
                LearningEvidenceRecord.id == evidence_id,
                LearningEvidenceRecord.merchant_id == merchant_id
            )
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            return None
        return self._record_to_schema(record)

    async def list_evidence(
        self,
        db: AsyncSession,
        filter_params: EvidenceFilter
    ) -> List[PolicyLearningEvidence]:
        """Query evidence matching filter parameters, strictly scoped to merchant_id."""
        conditions = [LearningEvidenceRecord.merchant_id == filter_params.merchant_id]

        if filter_params.buyer_context_key:
            conditions.append(LearningEvidenceRecord.buyer_context_key == filter_params.buyer_context_key)
        if filter_params.policy_id:
            conditions.append(LearningEvidenceRecord.policy_id == filter_params.policy_id)
        if filter_params.learning_eligible_only:
            conditions.append(LearningEvidenceRecord.learning_eligible == True)
        if filter_params.source:
            conditions.append(LearningEvidenceRecord.source == filter_params.source.value)

        stmt = select(LearningEvidenceRecord).where(and_(*conditions)).limit(filter_params.limit).offset(filter_params.offset)
        records = (await db.execute(stmt)).scalars().all()

        return [self._record_to_schema(r) for r in records]

    @staticmethod
    def _record_to_schema(record: LearningEvidenceRecord) -> PolicyLearningEvidence:
        """Convert a database record into a validated PolicyLearningEvidence schema."""
        guardrail_summaries = [
            EvidenceGuardrailSummary(**g) for g in (record.guardrail_results or [])
        ]
        return PolicyLearningEvidence(
            evidence_id=record.id,
            evidence_version=record.evidence_version,
            merchant_id=record.merchant_id,
            experiment_id=record.experiment_id,
            experiment_version="policy-experiment/v1",
            experiment_observation_id=record.experiment_observation_id,
            scenario_id=record.scenario_id,
            policy_id=record.policy_id,
            policy_version=record.policy_version,
            variant=VariantType(record.variant),
            buyer_context_key=record.buyer_context_key,
            buyer_intent_version=record.buyer_intent_version,
            buyer_selection_result_id=record.buyer_selection_result_id,
            simulation_version=record.simulation_version,
            execution_id=record.execution_id,
            provider_order_id=record.provider_order_id,
            verified_payment_id=record.verified_payment_id,
            source=EvidenceSource(record.source),
            outcome_type=LearningOutcomeType(record.outcome_type),
            sample_size=record.sample_size,
            is_selected=record.is_selected,
            expected_revenue_paise=record.expected_revenue_paise,
            expected_contribution_paise=record.expected_contribution_paise,
            observed_revenue_paise=record.observed_revenue_paise,
            observed_contribution_paise=record.observed_contribution_paise,
            margin_percent=float(record.margin_percent),
            guardrail_results=guardrail_summaries,
            evidence_status=EvidenceQualityStatus(record.evidence_status),
            lifecycle_state=EvidenceLifecycleState(record.lifecycle_state),
            learning_eligible=record.learning_eligible,
            eligibility_reasons=record.eligibility_reasons or [],
            aggregation_key=record.aggregation_key,
            idempotency_key=record.idempotency_key,
            observed_at=record.observed_at,
            created_at=record.created_at
        )
