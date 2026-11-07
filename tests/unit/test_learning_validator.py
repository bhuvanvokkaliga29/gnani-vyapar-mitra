"""Unit tests for LearningEvidenceValidator, provenance checks, and eligibility derivation."""

from datetime import datetime, timezone
import pytest
from services.experiments.schemas import ExperimentStatus, VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus,
    EvidenceGuardrailSummary
)
from services.learning.validator import LearningEvidenceValidator
from services.learning.errors import InvalidEvidenceError


@pytest.fixture
def valid_evidence():
    return PolicyLearningEvidence(
        evidence_id="evi_val_01",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas_travel",
        experiment_id="exp_01",
        experiment_observation_id="obs_01",
        scenario_id="scen_01",
        policy_id="prop_01",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=300000,
        expected_contribution_paise=150000,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key="agg_key",
        idempotency_key="idem_01",
        observed_at=datetime.now(timezone.utc)
    )


def test_validator_accepts_valid_evidence(valid_evidence):
    """Validator accepts compliant simulated evidence."""
    LearningEvidenceValidator.validate_provenance_and_integrity(valid_evidence)


def test_validator_rejects_unsupported_production_evidence(valid_evidence):
    """Validator strictly rejects PRODUCTION_OBSERVED in current test-mode foundation."""
    valid_evidence.source = EvidenceSource.PRODUCTION_OBSERVED
    with pytest.raises(InvalidEvidenceError) as exc:
        LearningEvidenceValidator.validate_provenance_and_integrity(valid_evidence)
    assert "PRODUCTION_OBSERVED evidence is unsupported" in str(exc.value)


def test_validator_rejects_simulated_claiming_observed_revenue(valid_evidence):
    """Validator strictly enforces separation of expected vs observed economics."""
    valid_evidence.source = EvidenceSource.SIMULATED
    valid_evidence.observed_revenue_paise = 300000  # Forbidden for simulated!
    with pytest.raises(InvalidEvidenceError) as exc:
        LearningEvidenceValidator.validate_provenance_and_integrity(valid_evidence)
    assert "SIMULATED evidence cannot contain observed revenue" in str(exc.value)


def test_validator_enforces_simulated_selection_not_payment_success(valid_evidence):
    """Invariant: SIMULATED_SELECTION != PAYMENT_SUCCESS."""
    valid_evidence.source = EvidenceSource.SIMULATED
    valid_evidence.outcome_type = LearningOutcomeType.PAYMENT_SUCCESS
    with pytest.raises(InvalidEvidenceError) as exc:
        LearningEvidenceValidator.validate_provenance_and_integrity(valid_evidence)
    assert "SIMULATED_SELECTION != PAYMENT_SUCCESS" in str(exc.value)


def test_validator_enforces_payment_success_requires_verified_payment_id(valid_evidence):
    """Invariant: PAYMENT_SUCCESS requires verified payment reference from webhooks."""
    valid_evidence.source = EvidenceSource.TEST_MODE_OBSERVED
    valid_evidence.execution_id = "exec_01"
    valid_evidence.outcome_type = LearningOutcomeType.PAYMENT_SUCCESS
    valid_evidence.verified_payment_id = None  # Missing!
    with pytest.raises(InvalidEvidenceError) as exc:
        LearningEvidenceValidator.validate_provenance_and_integrity(valid_evidence)
    assert "PAYMENT_SUCCESS requires verified_payment_id" in str(exc.value)


def test_derive_learning_eligibility_scenarios(valid_evidence):
    """Deterministic eligibility derivation across various experiment outcomes."""
    # 1. Valid and completed -> ELIGIBLE
    eligible, reasons = LearningEvidenceValidator.derive_learning_eligibility(
        valid_evidence,
        experiment_status=ExperimentStatus.COMPLETED
    )
    assert eligible is True
    assert "Evidence verified" in reasons[0]

    # 2. Experiment still running -> INELIGIBLE
    eligible, reasons = LearningEvidenceValidator.derive_learning_eligibility(
        valid_evidence,
        experiment_status=ExperimentStatus.RUNNING
    )
    assert eligible is False
    assert "not completed" in reasons[0]

    # 3. Quality status INSUFFICIENT_SAMPLE -> INELIGIBLE
    valid_evidence.evidence_status = EvidenceQualityStatus.INSUFFICIENT_SAMPLE
    eligible, reasons = LearningEvidenceValidator.derive_learning_eligibility(valid_evidence)
    assert eligible is False
    assert "below experiment minimum threshold" in reasons[0]

    # 4. Guardrail Failure -> INELIGIBLE
    valid_evidence.evidence_status = EvidenceQualityStatus.GUARDRAIL_FAILURE
    valid_evidence.guardrail_results = [
        EvidenceGuardrailSummary(
            guardrail_type="MIN_MARGIN_PERCENT",
            threshold_value=0.40,
            observed_value=0.25,
            passed=False,
            detail="Margin 25% breached 40% floor"
        )
    ]
    eligible, reasons = LearningEvidenceValidator.derive_learning_eligibility(valid_evidence)
    assert eligible is False
    assert any("guardrail failure" in r for r in reasons)
