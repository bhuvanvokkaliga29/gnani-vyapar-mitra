"""Unit tests for Phase 8.1 Learning Evidence schemas and contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus,
    EvidenceLifecycleState,
    BuyerContextDimensions,
    EvidenceGuardrailSummary,
    EvidenceFilter
)


def test_learning_evidence_schema_valid():
    """PolicyLearningEvidence accepts valid structured fields adhering to merchant-learning/v1."""
    evidence = PolicyLearningEvidence(
        evidence_id="evi_test_01",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas_travel",
        experiment_id="exp_01",
        experiment_version="policy-experiment/v1",
        experiment_observation_id="obs_01",
        scenario_id="scen_01",
        policy_id="prop_01",
        policy_version="merchant-policy/v1",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_travel_pack_tier_mid_abc123",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=349900,
        expected_contribution_paise=179900,
        margin_percent=51.41,
        evidence_status=EvidenceQualityStatus.VALID,
        lifecycle_state=EvidenceLifecycleState.LEARNING_ELIGIBLE,
        learning_eligible=True,
        eligibility_reasons=["Valid quality, complete provenance, satisfied guardrails."],
        aggregation_key="merch_atlas_travel:bck_travel_pack_tier_mid_abc123:prop_01:merchant-policy/v1",
        idempotency_key="evi_obs_exp_01_scen_01_TREATMENT",
        observed_at=datetime.now(timezone.utc)
    )

    assert evidence.evidence_version == "merchant-learning/v1"
    assert evidence.learning_eligible is True
    assert evidence.expected_revenue_paise == 349900
    assert evidence.source == EvidenceSource.SIMULATED


def test_learning_evidence_schema_forbids_extra_fields():
    """PolicyLearningEvidence strictly forbids extra fields (extra='forbid')."""
    with pytest.raises(ValidationError):
        PolicyLearningEvidence(
            evidence_id="evi_test_02",
            merchant_id="merch_atlas_travel",
            experiment_id="exp_01",
            experiment_observation_id="obs_01",
            scenario_id="scen_01",
            policy_id="prop_01",
            variant=VariantType.CONTROL,
            buyer_context_key="bck_travel_pack",
            source=EvidenceSource.SIMULATED,
            outcome_type=LearningOutcomeType.NO_SELECTION,
            is_selected=False,
            evidence_status=EvidenceQualityStatus.VALID,
            learning_eligible=False,
            aggregation_key="key",
            idempotency_key="idem",
            observed_at=datetime.now(timezone.utc),
            fake_reward_metric=999.0  # FORBIDDEN!
        )


def test_evidence_source_taxonomy_values():
    """Taxonomy explicitly separates SIMULATED, TEST_MODE_OBSERVED, and PRODUCTION_OBSERVED."""
    assert EvidenceSource.SIMULATED == "SIMULATED"
    assert EvidenceSource.TEST_MODE_OBSERVED == "TEST_MODE_OBSERVED"
    assert EvidenceSource.PRODUCTION_OBSERVED == "PRODUCTION_OBSERVED"


def test_learning_outcome_taxonomy_values():
    """Outcome taxonomy explicitly separates selection, order creation, and payment success."""
    assert LearningOutcomeType.SIMULATED_SELECTION == "SIMULATED_SELECTION"
    assert LearningOutcomeType.NO_SELECTION == "NO_SELECTION"
    assert LearningOutcomeType.ORDER_CREATED == "ORDER_CREATED"
    assert LearningOutcomeType.PAYMENT_SUCCESS == "PAYMENT_SUCCESS"
    assert LearningOutcomeType.PAYMENT_FAILURE == "PAYMENT_FAILURE"
    assert LearningOutcomeType.EXECUTION_REJECTED == "EXECUTION_REJECTED"
    assert LearningOutcomeType.EXPERIMENT_INCONCLUSIVE == "EXPERIMENT_INCONCLUSIVE"
