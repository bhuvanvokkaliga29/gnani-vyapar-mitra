"""Unit tests for Phase 7 Controlled Policy Experiments schemas and contracts."""

import pytest
from pydantic import ValidationError
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentHypothesis,
    ExperimentGuardrail,
    GuardrailType,
    ExperimentStatus,
    ExperimentObservation,
    VariantType,
    OutcomeType,
    VariantMetrics,
    MetricDelta,
    ExperimentResult,
    EvidenceStatus
)


def test_experiment_hypothesis_valid():
    """ExperimentHypothesis accepts valid structured fields and forbids unknown fields."""
    hyp = ExperimentHypothesis(
        population_description="Laptop buyers with budget <= ₹4,000",
        control_description="Single backpack at ₹2,999",
        treatment_description="Backpack + rain cover bundle at ₹3,499",
        expected_direction="HIGHER",
        primary_metric="EXPECTED_CONTRIBUTION_PER_SHOPPER",
        rationale="Value bundle increases AOV and contribution while satisfying warranty preference."
    )
    assert hyp.expected_direction == "HIGHER"

    # Forbids unknown fields
    with pytest.raises(ValidationError):
        ExperimentHypothesis(
            population_description="Pop",
            control_description="Ctrl",
            treatment_description="Treat",
            expected_direction="HIGHER",
            primary_metric="METRIC",
            rationale="Rat",
            unknown_random_field="INVALID"  # Forbidden!
        )


def test_policy_experiment_schema_forbids_extra_fields():
    """PolicyExperiment strictly forbids extra fields (extra='forbid')."""
    hyp = ExperimentHypothesis(
        population_description="Pop",
        control_description="Ctrl",
        treatment_description="Treat",
        expected_direction="HIGHER",
        primary_metric="EXPECTED_CONTRIBUTION_PER_SHOPPER",
        rationale="Rationale"
    )

    with pytest.raises(ValidationError):
        PolicyExperiment(
            experiment_id="exp_01",
            merchant_id="merch_atlas",
            name="Test Exp",
            control_policy_id="prop_01",
            treatment_policy_id="prop_02",
            control_proposal_snapshot={"merchant_id": "merch_atlas"},
            treatment_proposal_snapshot={"merchant_id": "merch_atlas"},
            hypothesis=hyp,
            fake_financial_override=99999  # Forbidden!
        )


def test_experiment_observation_contract():
    """ExperimentObservation accepts structured audit fields and records idempotency key."""
    obs = ExperimentObservation(
        observation_id="obs_test_01",
        experiment_id="exp_01",
        scenario_id="scen_01",
        variant=VariantType.TREATMENT,
        outcome_type=OutcomeType.SIMULATED,
        is_selected=True,
        revenue_paise=349900,
        contribution_paise=179900,
        margin_percent=51.41,
        idempotency_key="idem_exp_01_scen_01_TREATMENT"
    )
    assert obs.is_selected is True
    assert obs.revenue_paise == 349900
    assert obs.variant == VariantType.TREATMENT


def test_experiment_result_contract():
    """ExperimentResult encapsulates evidence status, winner, and metric deltas."""
    res = ExperimentResult(
        result_version="experiment-result/v1",
        experiment_id="exp_01",
        merchant_id="merch_atlas",
        status=ExperimentStatus.COMPLETED,
        evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE,
        winner=VariantType.TREATMENT,
        winner_rationale="Treatment demonstrated superior contribution.",
        sample_counts={"CONTROL": 25, "TREATMENT": 25},
        actual_control_count=25,
        actual_treatment_count=25,
        allocation_ratio=1.0,
        control_metrics=VariantMetrics(sample_size=25, selection_rate=0.48),
        treatment_metrics=VariantMetrics(sample_size=25, selection_rate=0.72),
        metric_deltas={
            "SELECTION_RATE": MetricDelta(
                metric_name="SELECTION_RATE",
                control_value=0.48,
                treatment_value=0.72,
                absolute_difference=0.24,
                relative_difference_percent=50.0,
                directionally_improved=True
            )
        },
        guardrail_results=[]
    )
    assert res.winner == VariantType.TREATMENT
    assert res.evidence_status == EvidenceStatus.SUFFICIENT_EVIDENCE
    assert res.actual_control_count == 25
    assert res.actual_treatment_count == 25
    assert res.allocation_ratio == 1.0
