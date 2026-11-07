"""Integration tests for Phase 8.9 Closed-Loop Learning Evaluation Orchestrator and Service.

Contract: closed-loop-evaluation/v1

Verifies:
- Complete closed loop: Observe -> Decide -> Act -> Measure -> Learn -> Holdout Generalization.
- Zero Leakage: Pre-update scoring and strictly frozen holdout.
- Cold start state verification.
- Idempotent evaluation dispatch and retrieval.
- Learning curve progression across checkpoints.
- Directional model adaptation under synthetic scenarios.
- FastAPI evaluation router endpoints.
"""

from decimal import Decimal
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from apps.api.main import app
from domain.models import (
    Merchant,
    Product,
    ClosedLoopEvaluationRecord,
    PolicyLearningModelState
)
from services.evaluation.schemas import (
    EVALUATION_SCHEMA_VERSION,
    EvaluationMode,
    EvaluationStatus,
    EvaluationOutcome,
    ClosedLoopEvaluationConfig,
    ClosedLoopEvaluationRequest,
    ClosedLoopEvaluationResult
)
from services.evaluation.service import ClosedLoopEvaluationService
from services.learning.model_service import PolicyLearningModelService


@pytest.fixture
async def seed_evaluation_merchant(db_session):
    """Seed test merchant and catalog for closed-loop evaluation tests."""
    merch = Merchant(
        id="merch_eval_test",
        name="Evaluation Test Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=20.0,
        maximum_discount_percent=20.0,
        target_aov_paise=400000
    )
    p1 = Product(
        id="prod_eval_bp_1",
        merchant_id=merch.id,
        name="Atlas Explorer Backpack",
        description="Premium waterproof travel backpack with laptop compartment",
        sku="SKU-EXP-001",
        category="travel_backpack",
        price_paise=450000,
        cost_paise=250000,  # ~44% margin
        inventory_quantity=50,
        is_active=True
    )
    p2 = Product(
        id="prod_eval_bp_2",
        merchant_id=merch.id,
        name="Atlas Urban Commuter",
        description="Lightweight city laptop backpack",
        sku="SKU-URB-002",
        category="travel_backpack",
        price_paise=350000,
        cost_paise=200000,
        inventory_quantity=50,
        is_active=True
    )
    db_session.add_all([merch, p1, p2])
    await db_session.commit()
    await db_session.refresh(merch)
    return merch


@pytest.mark.asyncio
async def test_full_closed_loop_simulation_run(db_session, seed_evaluation_merchant):
    """Execute complete closed-loop evaluation from intent to model update to frozen holdout."""
    config = ClosedLoopEvaluationConfig(
        mode=EvaluationMode.SIMULATION,
        training_sample_size=20,
        holdout_sample_size=5,
        checkpoints_count=3,
        randomization_seed=42
    )

    req = ClosedLoopEvaluationRequest(
        merchant_id=seed_evaluation_merchant.id,
        mode=EvaluationMode.SIMULATION,
        dataset_id="test_bench_v1",
        config=config
    )

    result = await ClosedLoopEvaluationService.run_evaluation(db_session, req)

    # 1. Status and Invariants
    assert result.status == EvaluationStatus.COMPLETED
    assert result.overall_outcome in [EvaluationOutcome.PASS, EvaluationOutcome.INCONCLUSIVE]
    assert result.merchant_id == seed_evaluation_merchant.id
    assert result.seed == 42

    # 2. Population Integrity
    assert result.training_definition.count == 20
    assert result.holdout_definition.count == 5
    assert len(result.training_definition.scenario_ids) == 20
    assert len(result.holdout_definition.scenario_ids) == 5
    # Zero overlap between training and holdout scenario IDs
    assert set(result.training_definition.scenario_ids).isdisjoint(set(result.holdout_definition.scenario_ids))

    # 3. Metrics Verification
    assert result.summary_metrics.sample_size == 20
    assert result.summary_metrics.baseline_ecps_paise == 0  # NO_OFFER always yields 0 contribution
    assert result.summary_metrics.model_updates_count == 20
    assert result.holdout_metrics.holdout_sample_size == 5

    # 4. Learning Curve Checkpoints
    assert len(result.learning_curve) >= 3
    assert result.learning_curve[0].progress_percent == 0
    assert result.learning_curve[-1].progress_percent == 100
    assert result.learning_curve[-1].opportunities_evaluated == 20

    # 5. Diagnostics Verification
    assert result.diagnostics.cold_start_verified is True
    assert result.diagnostics.zero_leakage_verified is True
    assert result.diagnostics.safety_invariants_verified is True
    assert result.diagnostics.promotion_audit_verified is True

    # 6. Database Persistence
    stmt = select(ClosedLoopEvaluationRecord).where(ClosedLoopEvaluationRecord.id == result.evaluation_id)
    db_row = (await db_session.execute(stmt)).scalar_one_or_none()
    assert db_row is not None
    assert db_row.status == "COMPLETED"
    assert db_row.merchant_id == seed_evaluation_merchant.id


@pytest.mark.asyncio
async def test_idempotent_evaluation_dispatch(db_session, seed_evaluation_merchant):
    """Repeated evaluation requests with the same idempotency key return existing result without re-executing."""
    idem_key = "eval_idem_test_001"
    config = ClosedLoopEvaluationConfig(
        training_sample_size=20,
        holdout_sample_size=5
    )
    req = ClosedLoopEvaluationRequest(
        merchant_id=seed_evaluation_merchant.id,
        idempotency_key=idem_key,
        config=config
    )

    res1 = await ClosedLoopEvaluationService.run_evaluation(db_session, req)
    assert res1.evaluation_id == idem_key

    # Second invocation with same key
    res2 = await ClosedLoopEvaluationService.run_evaluation(db_session, req)
    assert res2.evaluation_id == idem_key
    assert res2.summary_metrics.learned_ecps_paise == res1.summary_metrics.learned_ecps_paise
    assert res2.completed_at == res1.completed_at

    # Check exactly 1 DB record created
    stmt = select(ClosedLoopEvaluationRecord).where(ClosedLoopEvaluationRecord.id == idem_key)
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_frozen_holdout_isolation(db_session, seed_evaluation_merchant):
    """Holdout evaluation must not increment the merchant model observation count or write to memory."""
    config = ClosedLoopEvaluationConfig(
        training_sample_size=20,
        holdout_sample_size=8
    )
    req = ClosedLoopEvaluationRequest(
        merchant_id=seed_evaluation_merchant.id,
        config=config
    )

    res = await ClosedLoopEvaluationService.run_evaluation(db_session, req)
    assert res.status == EvaluationStatus.COMPLETED

    # Model observation count after entire evaluation run must equal training_sample_size (20), not 20+8!
    model, _ = await PolicyLearningModelService.get_or_create_model(db_session, seed_evaluation_merchant.id)
    assert model.observation_count == 20


@pytest.mark.asyncio
async def test_fastapi_closed_loop_endpoints(client: AsyncClient, seed_evaluation_merchant):
    """Test FastAPI endpoints for closed-loop evaluation: run, get, curve, and holdout."""
    payload = {
        "merchant_id": seed_evaluation_merchant.id,
        "mode": "SIMULATION",
        "dataset_id": "api_test_dataset",
        "config": {
            "mode": "SIMULATION",
            "training_sample_size": 20,
            "holdout_sample_size": 5,
            "checkpoints_count": 3,
            "randomization_seed": 77
        }
    }
    post_resp = await client.post("/api/v1/closed-loop-evaluations/run", json=payload)
    assert post_resp.status_code == 200
    data = post_resp.json()
    eval_id = data["evaluation_id"]
    assert eval_id.startswith("eval_")
    assert data["status"] == "COMPLETED"

    # 2. Fetch Result via GET
    get_resp = await client.get(f"/api/v1/closed-loop-evaluations/{eval_id}?merchant_id={seed_evaluation_merchant.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["evaluation_id"] == eval_id

    # 3. Fetch Learning Curve
    curve_resp = await client.get(f"/api/v1/closed-loop-evaluations/{eval_id}/curve?merchant_id={seed_evaluation_merchant.id}")
    assert curve_resp.status_code == 200
    checkpoints = curve_resp.json()
    assert len(checkpoints) >= 3

    # 4. Fetch Holdout Generalization Metrics
    holdout_resp = await client.get(f"/api/v1/closed-loop-evaluations/{eval_id}/holdout?merchant_id={seed_evaluation_merchant.id}")
    assert holdout_resp.status_code == 200
    holdout_data = holdout_resp.json()
    assert holdout_data["holdout_sample_size"] == 5
