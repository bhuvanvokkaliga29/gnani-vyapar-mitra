"""Unit tests for ExperimentMetricEngine in Phase 7."""

import pytest
from services.experiments.schemas import (
    ExperimentObservation,
    VariantType,
    ExperimentGuardrail,
    GuardrailType
)
from services.experiments.metrics import ExperimentMetricEngine


def test_metric_aggregation_single_variant():
    """ExperimentMetricEngine aggregates sample size, selection rate, contribution, and AOV."""
    observations = []
    # 10 decision instances: 5 selected, 5 not selected
    for i in range(10):
        is_sel = (i < 5)
        rev = 300000 if is_sel else 0
        contrib = 150000 if is_sel else 0
        margin = 50.0 if is_sel else 0.0

        observations.append(ExperimentObservation(
            observation_id=f"obs_{i}",
            experiment_id="exp_01",
            scenario_id=f"scen_{i}",
            variant=VariantType.TREATMENT,
            is_selected=is_sel,
            revenue_paise=rev,
            contribution_paise=contrib,
            margin_percent=margin,
            idempotency_key=f"idem_{i}"
        ))

    metrics = ExperimentMetricEngine.aggregate_variant_metrics(observations)

    assert metrics.sample_size == 10
    assert metrics.selection_count == 5
    assert metrics.selection_rate == 0.50
    assert metrics.total_revenue_paise == 1500000  # 5 * 300000
    assert metrics.aov_paise == 300000
    assert metrics.total_contribution_paise == 750000  # 5 * 150000
    assert metrics.expected_contribution_per_shopper_paise == 75000  # 750000 / 10
    assert metrics.average_margin_percent == 50.0


def test_metric_deltas_computation():
    """ExperimentMetricEngine computes absolute and relative deltas between Treatment and Control."""
    ctrl_obs = [
        ExperimentObservation(
            observation_id=f"ctrl_{i}",
            experiment_id="exp_01",
            scenario_id=f"scen_{i}",
            variant=VariantType.CONTROL,
            is_selected=(i < 3),  # 3 / 10 = 30%
            revenue_paise=300000 if (i < 3) else 0,
            contribution_paise=150000 if (i < 3) else 0,
            idempotency_key=f"ctrl_{i}"
        ) for i in range(10)
    ]

    treat_obs = [
        ExperimentObservation(
            observation_id=f"treat_{i}",
            experiment_id="exp_01",
            scenario_id=f"scen_{i}",
            variant=VariantType.TREATMENT,
            is_selected=(i < 6),  # 6 / 10 = 60%
            revenue_paise=350000 if (i < 6) else 0,
            contribution_paise=180000 if (i < 6) else 0,
            idempotency_key=f"treat_{i}"
        ) for i in range(10)
    ]

    ctrl_metrics = ExperimentMetricEngine.aggregate_variant_metrics(ctrl_obs)
    treat_metrics = ExperimentMetricEngine.aggregate_variant_metrics(treat_obs)

    deltas = ExperimentMetricEngine.compute_metric_deltas(ctrl_metrics, treat_metrics)

    sel_delta = deltas["SELECTION_RATE"]
    assert sel_delta.control_value == 0.30
    assert sel_delta.treatment_value == 0.60
    assert sel_delta.absolute_difference == 0.30
    assert sel_delta.relative_difference_percent == 100.0  # +100% relative lift
    assert sel_delta.directionally_improved is True


def test_guardrail_evaluation():
    """ExperimentMetricEngine evaluates guardrails and flags margin floor breach."""
    guardrails = [
        ExperimentGuardrail(
            guardrail_type=GuardrailType.MIN_MARGIN_PERCENT,
            threshold_value=0.40,  # 40% margin floor
            description="Min 40% margin"
        )
    ]

    # Variant with 45% margin -> PASS
    obs_pass = [
        ExperimentObservation(
            observation_id="obs_p",
            experiment_id="exp_1",
            scenario_id="s1",
            variant=VariantType.TREATMENT,
            is_selected=True,
            margin_percent=45.0,
            idempotency_key="p1"
        )
    ]
    metrics_pass = ExperimentMetricEngine.aggregate_variant_metrics(obs_pass)
    results_pass = ExperimentMetricEngine.evaluate_guardrails(guardrails, metrics_pass)
    assert results_pass[0].passed is True

    # Variant with 25% margin -> FAIL
    obs_fail = [
        ExperimentObservation(
            observation_id="obs_f",
            experiment_id="exp_1",
            scenario_id="s1",
            variant=VariantType.TREATMENT,
            is_selected=True,
            margin_percent=25.0,
            idempotency_key="f1"
        )
    ]
    metrics_fail = ExperimentMetricEngine.aggregate_variant_metrics(obs_fail)
    results_fail = ExperimentMetricEngine.evaluate_guardrails(guardrails, metrics_fail)
    assert results_fail[0].passed is False
    assert "breaches margin floor" in results_fail[0].detail
