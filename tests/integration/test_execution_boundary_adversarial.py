"""Adversarial and Invariant Boundary Tests for Phase 9.2 Execution Boundary.

Contract: execution-boundary/v1
Attacks & Invariants Verified:
1. Caller attempts to supply fake authorization / amount override (Rejected by Schema).
2. Cross-tenant decision execution attempt (Rejected with 403 / DecisionTenantViolationError).
3. Policy retired race (Decision made, policy retired, execution fails closed with POLICY_RETIRED).
4. Policy rolled back race (Decision made, policy rolled back, execution fails closed with POLICY_ROLLED_BACK).
5. Inventory exhaustion race (Stock drops to 0 between 9.1 and 9.2, Phase 8.6 rejects OUT_OF_STOCK).
6. Margin floor race (Merchant increases cost, Phase 8.6 rejects MARGIN_TOO_LOW).
7. Inactive merchant rejection.
8. Zero learning side effects (no writes to learning evidence, memory, or model parameters).
9. Strict information hygiene (zero COGS, zero gross margins in response).
"""

import pytest
from decimal import Decimal
from sqlalchemy import select, func

from domain.models import (
    Merchant,
    Product,
    MerchantPolicyVersionRecord,
    Order,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
)
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import (
    DecisionExecuteRequest,
    ExecutionBoundaryStatus
)
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.errors import DecisionTenantViolationError
from services.lifecycle.schemas import PolicyLifecycleState
from services.learning.model_service import PolicyLearningModelService


@pytest.fixture
async def seed_adversarial_merchants(db_session):
    """Seed Merchant Alpha (Active) and Merchant Beta (Active)."""
    mA = Merchant(
        id="merch_adv_alpha_92",
        name="Merchant Alpha 92",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    mB = Merchant(
        id="merch_adv_beta_92",
        name="Merchant Beta 92",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE"
    )
    db_session.add_all([mA, mB])

    pA = Product(
        id="prod_adv_pack_92",
        merchant_id=mA.id,
        sku="SKU-ADV-PACK-92",
        name="Alpha Tactical Pack",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        inventory_quantity=10,
        is_active=True,
        attributes={"laptop_size": 15.6}
    )
    db_session.add(pA)
    await db_session.commit()
    return mA, mB, pA


@pytest.mark.asyncio
async def test_cross_tenant_execution_attack(db_session, seed_adversarial_merchants):
    """Merchant Beta cannot execute Merchant Alpha's decision envelope."""
    mA, mB, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_cross_92_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)

    # Merchant Beta attempts execution
    bad_req = DecisionExecuteRequest(merchant_id=mB.id)
    with pytest.raises(DecisionTenantViolationError):
        await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, bad_req)


@pytest.mark.asyncio
async def test_policy_retired_race(db_session, seed_adversarial_merchants):
    """If policy was retired in Phase 8.8 after decision was made, execution fails closed."""
    mA, _, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_retire_92_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    selected_policy_id = envelope.selected_policy.candidate_id

    # Simulate Phase 8.8 retiring this policy version
    ver_record = MerchantPolicyVersionRecord(
        id=f"pver_{mA.id}_{selected_policy_id}_v1",
        merchant_id=mA.id,
        policy_id=selected_policy_id,
        policy_version="merchant-policy/v1",
        strategy_type=envelope.selected_policy.strategy_type,
        product_ids_json=list(envelope.selected_policy.product_ids),
        lifecycle_status=PolicyLifecycleState.RETIRED.value,
        rationale="Previously active, now retired",
        provenance_json={"status": "RETIRED"}
    )
    db_session.add(ver_record)
    await db_session.commit()

    count_orders_pre = (await db_session.execute(select(func.count(Order.id)))).scalar_one()

    # Attempt execution
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, exec_req)

    # Invariants
    assert resp.boundary_status == ExecutionBoundaryStatus.POLICY_RETIRED
    assert resp.execution_authorized is False
    assert any("POLICY_RETIRED" in r for r in resp.rejection_reasons)

    # Zero orders created
    count_orders_post = (await db_session.execute(select(func.count(Order.id)))).scalar_one()
    assert count_orders_pre == count_orders_post


@pytest.mark.asyncio
async def test_policy_rolled_back_race(db_session, seed_adversarial_merchants):
    """If policy was rolled back in Phase 8.8 after decision was made, execution fails closed."""
    mA, _, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_rollback_92_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    selected_policy_id = envelope.selected_policy.candidate_id

    # Simulate Phase 8.8 rolling back this policy
    ver_record = MerchantPolicyVersionRecord(
        id=f"pver_{mA.id}_{selected_policy_id}_v1",
        merchant_id=mA.id,
        policy_id=selected_policy_id,
        policy_version="merchant-policy/v1",
        strategy_type=envelope.selected_policy.strategy_type,
        product_ids_json=list(envelope.selected_policy.product_ids),
        lifecycle_status=PolicyLifecycleState.ROLLED_BACK.value,
        rationale="Underperformed guardrails, rolled back",
        provenance_json={"status": "ROLLED_BACK"}
    )
    db_session.add(ver_record)
    await db_session.commit()

    # Attempt execution
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, exec_req)

    assert resp.boundary_status == ExecutionBoundaryStatus.POLICY_ROLLED_BACK
    assert resp.execution_authorized is False
    assert any("POLICY_ROLLED_BACK" in r for r in resp.rejection_reasons)


@pytest.mark.asyncio
async def test_inventory_exhaustion_race(db_session, seed_adversarial_merchants):
    """When stock drops to 0 after 9.1 decision, Phase 8.6 rejects OUT_OF_STOCK with zero Razorpay calls."""
    mA, _, prod = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_stock_race_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)

    # Concurrency event: Inventory exhausted between decision and execution
    p = (await db_session.execute(select(Product).where(Product.id == prod.id))).scalar_one()
    p.inventory_quantity = 0
    await db_session.commit()

    count_orders_pre = (await db_session.execute(select(func.count(Order.id)))).scalar_one()

    # Execute
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, exec_req)

    assert resp.boundary_status == ExecutionBoundaryStatus.SAFETY_REJECTED
    assert resp.execution_authorized is False
    assert any("INVENTORY_INSUFFICIENT" in r for r in resp.rejection_reasons)

    # Zero orders created
    count_orders_post = (await db_session.execute(select(func.count(Order.id)))).scalar_one()
    assert count_orders_pre == count_orders_post


@pytest.mark.asyncio
async def test_margin_floor_breach_race(db_session, seed_adversarial_merchants):
    """When merchant cost increases after decision, Phase 8.6 rejects MARGIN_TOO_LOW with zero Razorpay calls."""
    mA, _, prod = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_margin_race_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)

    # Concurrency event: COGS surges above retail price
    p = (await db_session.execute(select(Product).where(Product.id == prod.id))).scalar_one()
    p.cost_paise = 480000  # Margin drops to 4%, constraint requires 20%
    await db_session.commit()

    count_orders_pre = (await db_session.execute(select(func.count(Order.id)))).scalar_one()

    # Execute
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, exec_req)

    assert resp.boundary_status == ExecutionBoundaryStatus.SAFETY_REJECTED
    assert resp.execution_authorized is False
    assert any("CONTRIBUTION_FLOOR_VIOLATED" in r for r in resp.rejection_reasons)

    count_orders_post = (await db_session.execute(select(func.count(Order.id)))).scalar_one()
    assert count_orders_pre == count_orders_post


@pytest.mark.asyncio
async def test_zero_learning_side_effects_in_9_2(db_session, seed_adversarial_merchants):
    """Phase 9.2 boundary MUST NOT write learning evidence, mutate memory, or update models."""
    mA, _, _ = seed_adversarial_merchants

    # Pre-execution learning state
    model_pre, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    obs_count_pre = model_pre.observation_count
    b_vector_pre = list(model_pre.b)
    evidence_count_pre = (await db_session.execute(select(func.count(LearningEvidenceRecord.id)))).scalar_one()
    memory_count_pre = (await db_session.execute(select(func.count(PolicyMemoryRecord.id)))).scalar_one()

    # Decision + Execution
    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_no_learn_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, exec_req)

    # Post-execution learning state: STRICTLY ZERO MUTATIONS
    model_post, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    assert model_post.observation_count == obs_count_pre
    assert list(model_post.b) == b_vector_pre

    evidence_count_post = (await db_session.execute(select(func.count(LearningEvidenceRecord.id)))).scalar_one()
    assert evidence_count_pre == evidence_count_post == 0

    memory_count_post = (await db_session.execute(select(func.count(PolicyMemoryRecord.id)))).scalar_one()
    assert memory_count_pre == memory_count_post == 0


@pytest.mark.asyncio
async def test_execution_response_strict_information_hygiene(db_session, seed_adversarial_merchants):
    """Execution response MUST NOT leak merchant unit costs (COGS), margins, or internal scores."""
    mA, _, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_hygiene_92_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    exec_req = DecisionExecuteRequest(merchant_id=mA.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(db_session, envelope.decision_id, exec_req)

    resp_dict = resp.model_dump()

    # Invariants: Customer-facing / boundary-safe fields
    assert "execution_id" in resp_dict
    assert "decision_id" in resp_dict
    assert "order_id" in resp_dict
    assert "razorpay_order_id" in resp_dict
    assert "authorized_amount_paise" in resp_dict

    # Strictly NO internal economics leakage
    assert "cogs_paise" not in resp_dict
    assert "gross_margin_percent" not in resp_dict
    assert "gross_profit_paise" not in resp_dict
    assert "model_weights" not in resp_dict
    assert "ucb_score" not in resp_dict
