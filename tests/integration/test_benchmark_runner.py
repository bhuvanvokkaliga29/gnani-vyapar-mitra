"""Integration Tests for Phase 11.1 Canonical Benchmark Harness.

Validates the 4 canonical smoke scenarios end-to-end:
1. SMOKE_HAPPY_PATH
2. SMOKE_PAYMENT_FAILURE
3. SMOKE_NO_OFFER
4. SMOKE_REPLAY_IDEMPOTENCY
Plus full suite execution and artifact production.
"""

import os
import tempfile
import pytest
from sqlalchemy import select

from domain.models import (
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    PolicyMemoryRecord,
)
from services.benchmark.schemas import (
    BenchmarkStatus,
    ScenarioCategory,
)
from services.benchmark.registry import (
    BenchmarkRegistry,
    SCENARIO_SMOKE_HAPPY_PATH,
    SCENARIO_SMOKE_PAYMENT_FAILURE,
    SCENARIO_SMOKE_NO_OFFER,
    SCENARIO_SMOKE_REPLAY_IDEMPOTENCY,
)
from services.benchmark.runner import CanonicalBenchmarkRunner
from services.benchmark.reporter import BenchmarkReporter


@pytest.mark.asyncio
async def test_smoke_happy_path_closed_loop(db_session):
    """Smoke Test 1: Full closed-loop happy path execution."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_HAPPY_PATH)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0

    obs = result.observed_state
    assert obs is not None
    assert obs.boundary_status == "EXECUTION_COMPLETED"
    assert obs.outcome_status == "PAYMENT_SUCCESS"
    assert obs.is_terminal is True
    assert obs.learning_eligible is True
    assert obs.reward_contribution_paise > 0
    assert obs.memory_id is not None


@pytest.mark.asyncio
async def test_smoke_payment_failure_closed_loop(db_session):
    """Smoke Test 2: Payment failure path preserves denominator with 0 reward."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_PAYMENT_FAILURE)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0

    obs = result.observed_state
    assert obs is not None
    assert obs.outcome_status == "PAYMENT_FAILED"
    assert obs.is_terminal is True
    assert obs.learning_eligible is True
    assert obs.reward_contribution_paise == 0


@pytest.mark.asyncio
async def test_smoke_no_offer_baseline(db_session):
    """Smoke Test 3: Unrealistic constraints select baseline NO_OFFER without boundary execution."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_NO_OFFER)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0

    obs = result.observed_state
    assert obs is not None
    assert obs.selected_strategy == "NO_OFFER"
    assert obs.execution_id is None
    assert obs.order_id is None


@pytest.mark.asyncio
async def test_smoke_replay_idempotency(db_session):
    """Smoke Test 4: Duplicate execution and outcome feedback are detected idempotently."""
    result = await CanonicalBenchmarkRunner.run_scenario(db_session, SCENARIO_SMOKE_REPLAY_IDEMPOTENCY)
    assert result.status == BenchmarkStatus.PASS
    assert result.assertions_failed == 0

    obs = result.observed_state
    assert obs is not None
    assert obs.is_duplicate_execution is True
    assert obs.is_duplicate_outcome is True


@pytest.mark.asyncio
async def test_smoke_suite_execution_and_artifacts(db_session):
    """Smoke Test 5: Execute all 4 smoke scenarios in a suite and generate run artifacts."""
    smoke_suite = [
        SCENARIO_SMOKE_HAPPY_PATH,
        SCENARIO_SMOKE_PAYMENT_FAILURE,
        SCENARIO_SMOKE_NO_OFFER,
        SCENARIO_SMOKE_REPLAY_IDEMPOTENCY,
    ]

    summary, results = await CanonicalBenchmarkRunner.run_suite(db_session, smoke_suite)

    assert summary.total_scenarios == 4
    assert summary.passed == 4
    assert summary.failed == 0
    assert summary.inconclusive == 0
    assert summary.reproducibility_status == "VERIFIED"

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifacts = BenchmarkReporter.save_run_artifacts(tmp_dir, summary, results)
        assert os.path.exists(artifacts["benchmark_summary"])
        assert os.path.exists(artifacts["scenario_results"])
        assert os.path.exists(artifacts["benchmark_run"])
        assert os.path.exists(artifacts["benchmark_run_report"])
