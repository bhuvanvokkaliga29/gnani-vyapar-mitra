"""Unit tests for Phase 8.9 Closed-Loop Learning Evaluation schemas and contracts.

Contract: closed-loop-evaluation/v1
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from services.evaluation.schemas import (
    EVALUATION_SCHEMA_VERSION,
    EvaluationMode,
    EvaluationStatus,
    EvaluationOutcome,
    PopulationDefinition,
    BaselineDefinition,
    EvaluationMetricSet,
    LearningCurveCheckpoint,
    HoldoutMetricSet,
    EvaluationDiagnostics,
    ClosedLoopEvaluationConfig,
    ClosedLoopEvaluationRequest,
    ClosedLoopEvaluationResult
)


def test_request_schema_defaults_and_validation():
    """Request requires valid merchant_id and enforces default configuration and version."""
    req = ClosedLoopEvaluationRequest(merchant_id="merch_test_1")
    assert req.merchant_id == "merch_test_1"
    assert req.mode == EvaluationMode.SIMULATION
    assert req.evaluation_version == EVALUATION_SCHEMA_VERSION
    assert req.dataset_id == "default_benchmark_v1"

    # Empty merchant_id rejected
    with pytest.raises(ValidationError):
        ClosedLoopEvaluationRequest(merchant_id="")


def test_config_validation_and_bounds():
    """Config enforces positive integer bounds and reasonable constraints."""
    cfg = ClosedLoopEvaluationConfig(
        training_sample_size=30,
        holdout_sample_size=10,
        randomization_seed=123
    )
    assert cfg.training_sample_size == 30
    assert cfg.holdout_sample_size == 10
    assert cfg.randomization_seed == 123
    assert cfg.config_version == EVALUATION_SCHEMA_VERSION

    # Invalid negative sample size rejected
    with pytest.raises(ValidationError):
        ClosedLoopEvaluationConfig(training_sample_size=0)


def test_result_schema_full_integrity():
    """ClosedLoopEvaluationResult preserves all metrics, checkpoints, and diagnostics immutably."""
    now = datetime.now(timezone.utc)
    summary = EvaluationMetricSet(
        sample_size=25,
        total_opportunities=25,
        baseline_ecps_paise=0,
        learned_ecps_paise=45000,
        absolute_delta_paise=45000,
        relative_delta=None,
        selection_rate=0.80,
        conversion_rate=0.80,
        exploration_rate=0.10,
        exposure_paise_consumed=15000,
        safety_rejection_rate=0.0,
        fallback_to_exploit_rate=0.0,
        model_updates_count=25,
        std_deviation_paise=12000.0,
        confidence_interval_95_paise=(40296.0, 49704.0)
    )

    holdout = HoldoutMetricSet(
        holdout_sample_size=5,
        holdout_ecps_paise=40000,
        baseline_ecps_paise=0,
        absolute_delta_paise=40000,
        relative_delta=None,
        holdout_selection_rate=0.80,
        holdout_safety_rejection_rate=0.0
    )

    diagnostics = EvaluationDiagnostics(
        cold_start_verified=True,
        exploration_bounds_verified=True,
        safety_invariants_verified=True,
        promotion_audit_verified=True,
        determinism_verified=True,
        tenant_isolation_verified=True,
        failure_injection_verified=True,
        zero_leakage_verified=True
    )

    res = ClosedLoopEvaluationResult(
        evaluation_id="eval_test_123",
        merchant_id="merch_test_1",
        mode=EvaluationMode.SIMULATION,
        status=EvaluationStatus.COMPLETED,
        overall_outcome=EvaluationOutcome.PASS,
        dataset_id="default_benchmark_v1",
        baseline_definition=BaselineDefinition(),
        training_definition=PopulationDefinition(dataset_id="ds1", count=25),
        evaluation_definition=PopulationDefinition(dataset_id="ds1", count=25),
        holdout_definition=PopulationDefinition(dataset_id="ds1", count=5),
        config=ClosedLoopEvaluationConfig(),
        seed=42,
        summary_metrics=summary,
        learning_curve=[],
        holdout_metrics=holdout,
        diagnostics=diagnostics,
        warnings=["Test warning"],
        failure_reasons=[],
        contract_versions={"closed_loop_evaluation": EVALUATION_SCHEMA_VERSION},
        created_at=now,
        completed_at=now
    )

    assert res.evaluation_id == "eval_test_123"
    assert res.overall_outcome == EvaluationOutcome.PASS
    assert res.summary_metrics.learned_ecps_paise == 45000
    assert res.holdout_metrics.holdout_ecps_paise == 40000
    assert res.diagnostics.zero_leakage_verified is True


def test_schema_extra_forbid():
    """All schemas forbid unrecognized extra fields."""
    with pytest.raises(ValidationError):
        ClosedLoopEvaluationRequest(merchant_id="m1", unauthorized_field="malicious_payload")
