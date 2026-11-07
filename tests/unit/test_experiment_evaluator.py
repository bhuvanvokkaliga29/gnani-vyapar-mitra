"""Unit tests for ExperimentEvaluator in Phase 7."""

import pytest
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentHypothesis,
    VariantMetrics,
    MetricDelta,
    GuardrailResult,
    GuardrailType,
    VariantType,
    EvidenceStatus
)
from services.experiments.evaluator import ExperimentEvaluator


@pytest.fixture
def base_experiment():
    return PolicyExperiment(
        experiment_id="exp_eval_test",
        merchant_id="merch_atlas",
        name="Eval Test",
        population_scenarios=["s1", "s2"],
        control_policy_id="p1",
        treatment_policy_id="p2",
        control_proposal_snapshot={"merchant_id": "merch_atlas", "status": "APPROVED"},
        treatment_proposal_snapshot={"merchant_id": "merch_atlas", "status": "APPROVED"},
        hypothesis=ExperimentHypothesis(
            population_description="Target",
            control_description="Ctrl",
            treatment_description="Treat",
            expected_direction="HIGHER",
            primary_metric="EXPECTED_CONTRIBUTION_PER_SHOPPER",
            rationale="Rational"
        ),
        primary_metric="EXPECTED_CONTRIBUTION_PER_SHOPPER"
    )


def test_evaluator_insufficient_sample(base_experiment):
    """ExperimentEvaluator flags INSUFFICIENT_SAMPLE when total samples < 10."""
    ctrl_metrics = VariantMetrics(sample_size=3)
    treat_metrics = VariantMetrics(sample_size=3)

    result = ExperimentEvaluator.evaluate_experiment(
        experiment=base_experiment,
        control_metrics=ctrl_metrics,
        treatment_metrics=treat_metrics,
        metric_deltas={},
        guardrail_results=[],
        min_sample_threshold=10
    )

    assert result.evidence_status == EvidenceStatus.INSUFFICIENT_SAMPLE
    assert result.winner is None
    assert "below minimum threshold" in result.winner_rationale


def test_evaluator_guardrail_failure_disqualifies_treatment(base_experiment):
    """When a guardrail fails, treatment is disqualified and Control is retained."""
    ctrl_metrics = VariantMetrics(sample_size=10, expected_contribution_per_shopper_paise=50000)
    treat_metrics = VariantMetrics(sample_size=10, expected_contribution_per_shopper_paise=80000)

    failed_guardrail = GuardrailResult(
        guardrail_type=GuardrailType.MIN_MARGIN_PERCENT,
        threshold_value=40.0,
        observed_value=25.0,
        passed=False,
        detail="Observed margin 25.0% breaches margin floor 40.0%"
    )

    result = ExperimentEvaluator.evaluate_experiment(
        experiment=base_experiment,
        control_metrics=ctrl_metrics,
        treatment_metrics=treat_metrics,
        metric_deltas={
            "EXPECTED_CONTRIBUTION_PER_SHOPPER": MetricDelta(
                metric_name="EXPECTED_CONTRIBUTION_PER_SHOPPER",
                control_value=50000.0,
                treatment_value=80000.0,
                absolute_difference=30000.0,
                directionally_improved=True
            )
        },
        guardrail_results=[failed_guardrail]
    )

    assert result.evidence_status == EvidenceStatus.GUARDRAIL_FAILURE
    assert result.winner == VariantType.CONTROL
    assert "disqualifies Treatment" in result.winner_rationale


def test_evaluator_decisive_treatment_winner(base_experiment):
    """When treatment outperforms primary metric and satisfies guardrails, Treatment wins."""
    ctrl_metrics = VariantMetrics(sample_size=15, expected_contribution_per_shopper_paise=50000)
    treat_metrics = VariantMetrics(sample_size=15, expected_contribution_per_shopper_paise=80000)

    passed_guardrail = GuardrailResult(
        guardrail_type=GuardrailType.MIN_MARGIN_PERCENT,
        threshold_value=40.0,
        observed_value=48.0,
        passed=True,
        detail="Observed margin meets floor"
    )

    result = ExperimentEvaluator.evaluate_experiment(
        experiment=base_experiment,
        control_metrics=ctrl_metrics,
        treatment_metrics=treat_metrics,
        metric_deltas={
            "EXPECTED_CONTRIBUTION_PER_SHOPPER": MetricDelta(
                metric_name="EXPECTED_CONTRIBUTION_PER_SHOPPER",
                control_value=50000.0,
                treatment_value=80000.0,
                absolute_difference=30000.0,
                relative_difference_percent=60.0,
                directionally_improved=True
            )
        },
        guardrail_results=[passed_guardrail]
    )

    assert result.evidence_status == EvidenceStatus.SUFFICIENT_EVIDENCE
    assert result.winner == VariantType.TREATMENT
    assert "Treatment demonstrated superior" in result.winner_rationale


def test_evaluator_tiny_delta_classified_as_inconclusive(base_experiment):
    """A tiny non-zero delta below the minimum detectable effect (e.g. 50.0% vs 50.1%) is INCONCLUSIVE."""
    ctrl_metrics = VariantMetrics(sample_size=15, selection_rate=0.500)
    treat_metrics = VariantMetrics(sample_size=15, selection_rate=0.501)

    # 0.2% relative difference, well below 2.0% MDE threshold
    result = ExperimentEvaluator.evaluate_experiment(
        experiment=base_experiment,
        control_metrics=ctrl_metrics,
        treatment_metrics=treat_metrics,
        metric_deltas={
            "EXPECTED_CONTRIBUTION_PER_SHOPPER": MetricDelta(
                metric_name="EXPECTED_CONTRIBUTION_PER_SHOPPER",
                control_value=500.0,
                treatment_value=501.0,
                absolute_difference=1.0,
                relative_difference_percent=0.20,
                directionally_improved=True
            )
        },
        guardrail_results=[]
    )

    assert result.evidence_status == EvidenceStatus.INCONCLUSIVE
    assert result.winner is None
    assert "within the uncertainty / minimum detectable effect threshold" in result.winner_rationale


def test_evaluator_records_actual_allocation_counts_and_ratio(base_experiment):
    """Evaluator records observed allocation counts and ratio rather than assuming exact 50/50."""
    ctrl_metrics = VariantMetrics(sample_size=12)
    treat_metrics = VariantMetrics(sample_size=14)

    result = ExperimentEvaluator.evaluate_experiment(
        experiment=base_experiment,
        control_metrics=ctrl_metrics,
        treatment_metrics=treat_metrics,
        metric_deltas={},
        guardrail_results=[]
    )

    assert result.actual_control_count == 12
    assert result.actual_treatment_count == 14
    assert result.allocation_ratio == 1.167  # 14 / 12 = 1.167
