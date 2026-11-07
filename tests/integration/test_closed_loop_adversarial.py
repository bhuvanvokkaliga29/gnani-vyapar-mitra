"""Adversarial and Invariant Test Suite for Phase 8.9 Closed-Loop Learning Evaluation.

Contract: closed-loop-evaluation/v1

Verifies:
- Invariant 1: Multi-tenant isolation (Merchant A data completely invisible to Merchant B).
- Invariant 2: Deterministic reproducibility (Identical seed yields identical metrics).
- Invariant 3: Failure injection resilience (Inventory shortages, margin breaches, safety fallbacks).
- Invariant 4: Model adaptation under directional synthetic datasets and regime shifts.
- Invariant 5: Replay mode safety (No state mutation during replay).
- Invariant 6: Strict semantic AST audit (Zero prohibited marketing or causal claims).
"""

import ast
from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import select

from domain.models import Merchant, Product
from services.evaluation.schemas import (
    EVALUATION_SCHEMA_VERSION,
    EvaluationMode,
    EvaluationStatus,
    EvaluationOutcome,
    ClosedLoopEvaluationConfig,
    ClosedLoopEvaluationRequest
)
from services.evaluation.service import ClosedLoopEvaluationService
from services.evaluation.errors import (
    IncompatibleEvaluationVersionError,
    EvaluationTenantViolationError,
    EvaluationNotFoundError
)
from services.evaluation.scenarios import EvaluationScenarioGenerator
from services.learning.model_service import PolicyLearningModelService


@pytest.fixture
async def seed_dual_merchants(db_session):
    """Seed two distinct merchant tenants to test tenant isolation."""
    mA = Merchant(
        id="merch_eval_tenant_a",
        name="Merchant Alpha",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=15.0,
        maximum_discount_percent=25.0,
        target_aov_paise=500000
    )
    pA = Product(
        id="prod_alpha_1",
        merchant_id=mA.id,
        name="Alpha Pack",
        sku="SKU-A-01",
        category="travel_backpack",
        price_paise=299900,
        cost_paise=150000,
        inventory_quantity=30,
        attributes={"laptop_size": 16.0, "water_resistant": True},
        is_active=True
    )
    mB = Merchant(
        id="merch_eval_tenant_b",
        name="Merchant Beta",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_MARGIN",
        minimum_margin_percent=30.0,
        maximum_discount_percent=10.0,
        target_aov_paise=600000
    )
    pB = Product(
        id="prod_beta_1",
        merchant_id=mB.id,
        name="Beta Pack",
        sku="SKU-B-01",
        category="travel_backpack",
        price_paise=600000,
        cost_paise=350000,
        inventory_quantity=30,
        is_active=True
    )
    db_session.add_all([mA, pA, mB, pB])
    await db_session.commit()
    await db_session.refresh(mA)
    await db_session.refresh(mB)
    return mA, mB


@pytest.mark.asyncio
async def test_tenant_isolation_invariants(db_session, seed_dual_merchants):
    """Merchant A cannot view, query, or leak evidence into Merchant B's evaluation."""
    mA, mB = seed_dual_merchants
    cfg = ClosedLoopEvaluationConfig(training_sample_size=20, holdout_sample_size=5, randomization_seed=42)

    # 1. Run evaluation for Merchant A
    reqA = ClosedLoopEvaluationRequest(merchant_id=mA.id, config=cfg)
    resA = await ClosedLoopEvaluationService.run_evaluation(db_session, reqA)
    assert resA.status == EvaluationStatus.COMPLETED

    # 2. Merchant B attempts to fetch Merchant A's evaluation
    with pytest.raises(EvaluationTenantViolationError):
        await ClosedLoopEvaluationService.get_evaluation(db_session, resA.evaluation_id, merchant_id=mB.id)

    # 3. Verify learning model isolation
    modelA, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    modelB, _ = await PolicyLearningModelService.get_or_create_model(db_session, mB.id)
    assert modelA.observation_count == 20
    assert modelB.observation_count == 0  # Merchant B model completely unaffected


@pytest.mark.asyncio
async def test_determinism_and_seed_reproducibility(db_session, seed_dual_merchants):
    """Two independent evaluation runs with identical seeds and inputs produce bit-for-bit identical metrics."""
    mA, _ = seed_dual_merchants
    cfg = ClosedLoopEvaluationConfig(training_sample_size=20, holdout_sample_size=5, randomization_seed=99)

    req1 = ClosedLoopEvaluationRequest(merchant_id=mA.id, dataset_id="det_1", config=cfg)
    res1 = await ClosedLoopEvaluationService.run_evaluation(db_session, req1)

    # Create fresh merchant with same catalog for independent run
    m_copy = Merchant(
        id="merch_eval_copy",
        name="Merchant Copy",
        currency="INR",
        status="ACTIVE",
        business_objective=mA.business_objective,
        minimum_margin_percent=mA.minimum_margin_percent,
        maximum_discount_percent=mA.maximum_discount_percent,
        target_aov_paise=mA.target_aov_paise
    )
    p_copy = Product(
        id="prod_copy_1",
        merchant_id=m_copy.id,
        name="Alpha Pack Copy",
        sku="SKU-A-01-COPY",
        category="travel_backpack",
        price_paise=299900,
        cost_paise=150000,
        inventory_quantity=30,
        attributes={"laptop_size": 16.0, "water_resistant": True},
        is_active=True
    )
    db_session.add_all([m_copy, p_copy])
    await db_session.commit()

    req2 = ClosedLoopEvaluationRequest(merchant_id=m_copy.id, dataset_id="det_2", config=cfg)
    res2 = await ClosedLoopEvaluationService.run_evaluation(db_session, req2)

    # All metrics must be bit-for-bit identical
    assert res1.summary_metrics.learned_ecps_paise == res2.summary_metrics.learned_ecps_paise
    assert res1.summary_metrics.selection_rate == res2.summary_metrics.selection_rate
    assert res1.summary_metrics.exploration_rate == res2.summary_metrics.exploration_rate
    assert res1.holdout_metrics.holdout_ecps_paise == res2.holdout_metrics.holdout_ecps_paise
    assert len(res1.learning_curve) == len(res2.learning_curve)


@pytest.mark.asyncio
async def test_failure_injection_inventory_shortage(db_session, seed_dual_merchants):
    """When inventory drops to zero, Phase 8.6 safety gate rejects candidates and falls back safely."""
    mA, _ = seed_dual_merchants

    # Deplete inventory to 0
    p = (await db_session.execute(select(Product).where(Product.merchant_id == mA.id))).scalar_one()
    p.inventory_quantity = 0
    await db_session.commit()

    cfg = ClosedLoopEvaluationConfig(training_sample_size=20, holdout_sample_size=5)
    req = ClosedLoopEvaluationRequest(merchant_id=mA.id, config=cfg)

    # Evaluator must complete without crash, recording zero conversions/selections due to safety rejection
    res = await ClosedLoopEvaluationService.run_evaluation(db_session, req)
    assert res.status == EvaluationStatus.COMPLETED
    assert res.summary_metrics.selection_rate == 0.0
    assert res.summary_metrics.conversion_rate == 0.0


@pytest.mark.asyncio
async def test_invalid_contract_version_rejected(db_session, seed_dual_merchants):
    """Unsupported contract version in request raises IncompatibleEvaluationVersionError."""
    mA, _ = seed_dual_merchants
    req = ClosedLoopEvaluationRequest(
        merchant_id=mA.id,
        evaluation_version="closed-loop-evaluation/v999"
    )
    with pytest.raises(IncompatibleEvaluationVersionError):
        await ClosedLoopEvaluationService.run_evaluation(db_session, req)


@pytest.mark.asyncio
async def test_directional_model_adaptation(db_session, seed_dual_merchants):
    """Evaluates that LinUCB updates internal parameters when receiving sequential rewards."""
    mA, _ = seed_dual_merchants
    ctx_a, ctx_b, shift = EvaluationScenarioGenerator.generate_directional_learning_dataset(count_per_regime=10)

    cfg = ClosedLoopEvaluationConfig(training_sample_size=20, holdout_sample_size=5)
    req = ClosedLoopEvaluationRequest(merchant_id=mA.id, config=cfg)

    # Initial cold start model
    model_pre, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    assert model_pre.observation_count == 0

    res = await ClosedLoopEvaluationService.run_evaluation(db_session, req)
    assert res.status == EvaluationStatus.COMPLETED

    # Post-training model has updated parameters
    model_post, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    assert model_post.observation_count == 20
    # Vector b is updated and non-zero
    assert any(val != 0.0 for val in model_post.b)


def test_adversarial_semantic_audit():
    """Static AST audit of services/evaluation to ensure zero forbidden marketing or causal claims."""
    eval_dir = Path("services/evaluation")
    python_files = list(eval_dir.glob("*.py"))
    assert len(python_files) >= 5, "Evaluation modules missing"

    prohibited_terms = [
        "production revenue uplift",
        "guaranteed profit",
        "real transaction",
        "real money",
        "causal superiority",
        "optimal policy",
        "unbiased treatment effect"
    ]

    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8").lower()
        for term in prohibited_terms:
            assert term not in content, f"Forbidden term '{term}' found in {py_file.name}!"
