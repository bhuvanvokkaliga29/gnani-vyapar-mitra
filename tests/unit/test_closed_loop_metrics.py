"""Unit tests for Phase 8.9 Metric Calculator and Statistical Evaluator."""

import pytest
from services.evaluation.metrics import EvaluationMetricCalculator
from services.evaluation.schemas import (
    ClosedLoopEvaluationConfig,
    EvaluationOutcome,
    EvaluationMetricSet,
    HoldoutMetricSet
)


def test_ecps_calculation_with_zero_retained():
    """Zero-contribution non-selection trials must be retained in the denominator."""
    # 2 opportunities: 1 selected with 50000 paise contribution, 1 not selected with 0 paise
    contributions = [50000, 0]
    ecps = EvaluationMetricCalculator.calculate_ecps(contributions)
    assert ecps == 25000

    # Negative contribution retained
    contributions_neg = [50000, -10000]
    ecps_neg = EvaluationMetricCalculator.calculate_ecps(contributions_neg)
    assert ecps_neg == 20000


def test_std_deviation_and_confidence_interval():
    """Calculates sample standard deviation and standard 95% confidence interval."""
    contributions = [10000, 20000, 30000, 40000, 50000]
    std = EvaluationMetricCalculator.calculate_std_deviation(contributions)
    assert std == pytest.approx(15811.39, abs=0.1)

    ci = EvaluationMetricCalculator.calculate_confidence_interval_95(contributions)
    assert ci[0] < 30000.0 < ci[1]


def test_outcome_insufficient_evidence_when_small_sample():
    """Sample size < 20 must return INSUFFICIENT_EVIDENCE."""
    cfg = ClosedLoopEvaluationConfig()
    summary = EvaluationMetricCalculator.assemble_metric_set(
        contributions_paise=[50000] * 15,
        baseline_contributions_paise=[0] * 15,
        selections=[True] * 15,
        conversions=[True] * 15,
        exploration_modes=["EXPLOIT"] * 15,
        exposures_paise=[0] * 15,
        safety_rejections=[False] * 15,
        fallbacks_to_exploit=[False] * 15,
        model_updates_count=15
    )
    holdout = EvaluationMetricCalculator.assemble_holdout_metrics(
        holdout_contributions_paise=[50000] * 5,
        holdout_baseline_contributions_paise=[0] * 5,
        holdout_selections=[True] * 5,
        holdout_safety_rejections=[False] * 5
    )
    outcome, reasons = EvaluationMetricCalculator.determine_evaluation_outcome(summary, holdout, cfg)
    assert outcome == EvaluationOutcome.INSUFFICIENT_EVIDENCE
    assert any("20 minimum" in r for r in reasons)


def test_outcome_pass_when_uplift_and_generalization_confirmed():
    """PASS is awarded when sample size >= 20, learned ECPS > baseline, and holdout ECPS >= baseline."""
    cfg = ClosedLoopEvaluationConfig()
    summary = EvaluationMetricCalculator.assemble_metric_set(
        contributions_paise=[40000] * 25,
        baseline_contributions_paise=[0] * 25,
        selections=[True] * 25,
        conversions=[True] * 25,
        exploration_modes=["EXPLOIT"] * 25,
        exposures_paise=[0] * 25,
        safety_rejections=[False] * 25,
        fallbacks_to_exploit=[False] * 25,
        model_updates_count=25
    )
    holdout = EvaluationMetricCalculator.assemble_holdout_metrics(
        holdout_contributions_paise=[35000] * 10,
        holdout_baseline_contributions_paise=[0] * 10,
        holdout_selections=[True] * 10,
        holdout_safety_rejections=[False] * 10
    )
    outcome, reasons = EvaluationMetricCalculator.determine_evaluation_outcome(summary, holdout, cfg)
    assert outcome == EvaluationOutcome.PASS
    assert len(reasons) == 0


def test_outcome_fail_when_overfitting_detected():
    """FAIL is awarded when training improves but holdout degrades significantly."""
    cfg = ClosedLoopEvaluationConfig(require_holdout_non_negative=True)
    summary = EvaluationMetricCalculator.assemble_metric_set(
        contributions_paise=[50000] * 25,
        baseline_contributions_paise=[0] * 25,
        selections=[True] * 25,
        conversions=[True] * 25,
        exploration_modes=["EXPLOIT"] * 25,
        exposures_paise=[0] * 25,
        safety_rejections=[False] * 25,
        fallbacks_to_exploit=[False] * 25,
        model_updates_count=25
    )
    # Holdout has negative contribution relative to baseline
    holdout = EvaluationMetricCalculator.assemble_holdout_metrics(
        holdout_contributions_paise=[-5000] * 10,
        holdout_baseline_contributions_paise=[0] * 10,
        holdout_selections=[True] * 10,
        holdout_safety_rejections=[False] * 10
    )
    outcome, reasons = EvaluationMetricCalculator.determine_evaluation_outcome(summary, holdout, cfg)
    assert outcome == EvaluationOutcome.FAIL
    assert any("Holdout ECPS" in r for r in reasons)


def test_outcome_fail_when_safety_rejection_exceeded():
    """FAIL is awarded when safety rejection rate exceeds configured ceiling."""
    cfg = ClosedLoopEvaluationConfig(max_tolerated_safety_rejections_percent=10.0)
    summary = EvaluationMetricCalculator.assemble_metric_set(
        contributions_paise=[40000] * 20,
        baseline_contributions_paise=[0] * 20,
        selections=[True] * 20,
        conversions=[True] * 20,
        exploration_modes=["EXPLOIT"] * 20,
        exposures_paise=[0] * 20,
        safety_rejections=[True] * 5 + [False] * 15,  # 25% safety rejection > 10%
        fallbacks_to_exploit=[True] * 5 + [False] * 15,
        model_updates_count=20
    )
    holdout = EvaluationMetricCalculator.assemble_holdout_metrics(
        holdout_contributions_paise=[40000] * 10,
        holdout_baseline_contributions_paise=[0] * 10,
        holdout_selections=[True] * 10,
        holdout_safety_rejections=[False] * 10
    )
    outcome, reasons = EvaluationMetricCalculator.determine_evaluation_outcome(summary, holdout, cfg)
    assert outcome == EvaluationOutcome.FAIL
    assert any("Safety rejection rate" in r for r in reasons)
