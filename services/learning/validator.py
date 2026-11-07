"""Learning Evidence Validator: Enforces provenance, outcome invariants, and deterministic eligibility."""

from typing import Tuple, List, Optional
from services.experiments.schemas import ExperimentStatus
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus
)
from services.learning.errors import InvalidEvidenceError


class LearningEvidenceValidator:
    """Deterministic validation and eligibility derivation for merchant learning evidence."""

    @classmethod
    def validate_provenance_and_integrity(cls, evidence: PolicyLearningEvidence) -> None:
        """Validate provenance linkages, taxonomy constraints, and economic separations."""
        # 1. Scoping & Identifiers
        if not evidence.merchant_id:
            raise InvalidEvidenceError("Evidence merchant_id must not be empty.")
        if not evidence.experiment_id:
            raise InvalidEvidenceError("Evidence experiment_id must not be empty.")
        if not evidence.policy_id:
            raise InvalidEvidenceError("Evidence policy_id must not be empty.")
        if not evidence.scenario_id:
            raise InvalidEvidenceError("Evidence scenario_id must not be empty.")
        if not evidence.buyer_context_key:
            raise InvalidEvidenceError("Evidence buyer_context_key must not be empty.")

        # 2. Source Taxonomy Enforcement
        if evidence.source == EvidenceSource.PRODUCTION_OBSERVED:
            raise InvalidEvidenceError(
                "PRODUCTION_OBSERVED evidence is unsupported and forbidden in the current test-mode foundation."
            )

        # 3. Simulated vs. Observed Economic Separation
        if evidence.source == EvidenceSource.SIMULATED:
            if evidence.observed_revenue_paise is not None or evidence.observed_contribution_paise is not None:
                raise InvalidEvidenceError(
                    "SIMULATED evidence cannot contain observed revenue or contribution. "
                    "Expected and observed economics must be strictly separated."
                )
            if evidence.provider_order_id is not None or evidence.verified_payment_id is not None:
                raise InvalidEvidenceError(
                    "SIMULATED evidence cannot contain provider_order_id or verified_payment_id."
                )

        # 4. Test-Mode Execution Provenance
        if evidence.source == EvidenceSource.TEST_MODE_OBSERVED:
            if not evidence.execution_id:
                raise InvalidEvidenceError("TEST_MODE_OBSERVED evidence requires valid execution_id.")

        # 5. Outcome Invariant Enforcement
        # INVARIANT: ORDER_CREATED != PAYMENT_SUCCESS
        # INVARIANT: SIMULATED_SELECTION != PAYMENT_SUCCESS
        if evidence.outcome_type == LearningOutcomeType.PAYMENT_SUCCESS:
            if evidence.source == EvidenceSource.SIMULATED:
                raise InvalidEvidenceError(
                    "SIMULATED_SELECTION != PAYMENT_SUCCESS: Simulated evidence can never claim PAYMENT_SUCCESS."
                )
            if not evidence.verified_payment_id:
                raise InvalidEvidenceError(
                    "PAYMENT_SUCCESS requires verified_payment_id from authoritative webhook reconciliation."
                )

        if evidence.outcome_type == LearningOutcomeType.ORDER_CREATED:
            if not evidence.provider_order_id:
                raise InvalidEvidenceError(
                    "ORDER_CREATED outcome requires provider_order_id from Phase 5 Execution Gate."
                )

    @classmethod
    def derive_learning_eligibility(
        cls,
        evidence: PolicyLearningEvidence,
        experiment_status: ExperimentStatus = ExperimentStatus.COMPLETED
    ) -> Tuple[bool, List[str]]:
        """Deterministically derive learning_eligible status and audit reasons.
        
        The LLM has zero authority over this field.
        """
        reasons = []

        # 1. Experiment Completion Check
        if experiment_status != ExperimentStatus.COMPLETED:
            reasons.append(f"Originating experiment is not completed (status: {experiment_status.value}).")

        # 2. Quality Status Checks
        if evidence.evidence_status == EvidenceQualityStatus.INSUFFICIENT_SAMPLE:
            reasons.append("Evidence sample size is below experiment minimum threshold.")
        elif evidence.evidence_status == EvidenceQualityStatus.INCONCLUSIVE:
            reasons.append("Experiment comparison failed to establish statistically meaningful difference.")
        elif evidence.evidence_status == EvidenceQualityStatus.GUARDRAIL_FAILURE:
            reasons.append("Variant breached commercial safety guardrails.")
        elif evidence.evidence_status == EvidenceQualityStatus.INVALID:
            reasons.append("Evidence flagged as invalid or integrity broken.")

        # 3. Guardrail Breach Check
        failed_guardrails = [g for g in evidence.guardrail_results if not g.passed]
        if failed_guardrails:
            reasons.append(f"Observed {len(failed_guardrails)} guardrail failure(s).")

        # 4. Source Validity
        if evidence.source not in [EvidenceSource.SIMULATED, EvidenceSource.TEST_MODE_OBSERVED]:
            reasons.append(f"Source '{evidence.source.value}' is not eligible for commercial policy learning.")

        # 5. Sample Size
        if evidence.sample_size < 1:
            reasons.append("Sample size must be at least 1.")

        is_eligible = (len(reasons) == 0 and evidence.evidence_status == EvidenceQualityStatus.VALID)

        if is_eligible:
            reasons.append("Evidence verified: valid quality, complete provenance, satisfied guardrails.")

        return is_eligible, reasons
