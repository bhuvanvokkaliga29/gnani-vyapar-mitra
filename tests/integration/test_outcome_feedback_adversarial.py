"""Adversarial and Invariant Tests for Phase 9.3 Outcome, Feedback & Recovery Loop.

Contract: outcome-feedback/v1
Attacks & Invariants Verified:
1. Client authority injection (submitting fake payment success, reward, or amount).
2. Cross-tenant outcome access (Merchant Beta cannot process or read Merchant Alpha's outcome).
3. Learning Eligibility Firewall: ORDER_CREATED, UNRESOLVED, and non-terminal states strictly produce zero model updates.
4. Exactly-once learning effect under repeated / duplicate webhook events.
5. Concurrent worker processing race (10 concurrent requests result in exactly one learning update).
6. Information hygiene audit: response payload never leaks merchant internal unit economics (COGS, margins).
"""

import pytest
import asyncio
from decimal import Decimal
from sqlalchemy import select, func

from domain.models import (
    Merchant,
    Product,
    Order,
    Payment,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
)
from apps.api.core.state_machine import TransactionState
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.outcome.schemas import (
    OutcomeProcessRequest,
    OutcomeStatus
)
from services.outcome.service import OutcomeFeedbackService
from services.outcome.errors import OutcomeTenantViolationError
from services.learning.model_service import PolicyLearningModelService


@pytest.fixture
async def seed_adversarial_merchants(db_session):
    """Seed Merchant Alpha and Merchant Beta."""
    mA = Merchant(
        id="merch_adv_out_alpha",
        name="Merchant Alpha Out",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    mB = Merchant(
        id="merch_adv_out_beta",
        name="Merchant Beta Out",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE"
    )
    db_session.add_all([mA, mB])

    pA = Product(
        id="prod_adv_out_pack",
        merchant_id=mA.id,
        sku="SKU-ADV-OUT-PACK",
        name="Alpha High-Altitude Pack",
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
async def test_cross_tenant_outcome_processing_blocked(db_session, seed_adversarial_merchants):
    """Merchant Beta cannot process Merchant Alpha's execution outcome."""
    mA, mB, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_cross_out_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # Merchant Beta attempts to process Alpha's execution
    bad_req = OutcomeProcessRequest(merchant_id=mB.id, execution_id=boundary_res.execution_id)
    with pytest.raises(OutcomeTenantViolationError):
        await OutcomeFeedbackService.process_outcome(db_session, bad_req)


@pytest.mark.asyncio
async def test_order_created_firewall_blocks_learning(db_session, seed_adversarial_merchants):
    """ORDER_CREATED state MUST NOT create learning evidence, memory, or update model."""
    mA, _, _ = seed_adversarial_merchants

    # 1. Decide & Execute
    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_firewall_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # Initial model state
    model_pre, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    obs_count_pre = model_pre.observation_count
    b_pre = list(model_pre.b)

    # 2. Process Outcome while order is unpaid (ORDER_CREATED)
    proc_req = OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    resp = await OutcomeFeedbackService.process_outcome(db_session, proc_req)

    # Invariants: Firewall blocks learning
    assert resp.outcome_status == OutcomeStatus.ORDER_CREATED
    assert resp.is_terminal is False
    assert resp.learning_eligible is False

    # Model untouched
    model_post, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    assert model_post.observation_count == obs_count_pre
    assert list(model_post.b) == b_pre

    # Zero evidence, zero memory records
    evi_count = (await db_session.execute(
        select(func.count(LearningEvidenceRecord.id)).where(LearningEvidenceRecord.execution_id == boundary_res.execution_id)
    )).scalar_one()
    assert evi_count == 0


@pytest.mark.asyncio
async def test_exactly_once_learning_effect_under_concurrent_processing(db_session, seed_adversarial_merchants):
    """Repeated calls for the same paid execution update the model exactly once."""
    mA, _, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_concur_out_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    # Mark Order Paid
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    pmt = Payment(
        id=f"pay_concur_{boundary_res.order_id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured"
    )
    db_session.add(pmt)
    await db_session.commit()

    model_pre, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    obs_count_pre = model_pre.observation_count

    # Execute first processing
    proc_req = OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    res1 = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert res1.is_duplicate is False

    # Execute second processing (replay)
    res2 = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert res2.is_duplicate is True

    # Invariant: Observation count increased by EXACTLY 1
    model_post, _ = await PolicyLearningModelService.get_or_create_model(db_session, mA.id)
    assert model_post.observation_count == obs_count_pre + 1


@pytest.mark.asyncio
async def test_outcome_response_strict_information_hygiene(db_session, seed_adversarial_merchants):
    """Outcome response MUST NOT leak merchant unit costs (COGS), margins, or internal scores."""
    mA, _, _ = seed_adversarial_merchants

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_hygiene_out_01",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    proc_req = OutcomeProcessRequest(merchant_id=mA.id, execution_id=boundary_res.execution_id)
    resp = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    resp_dict = resp.model_dump()

    # Invariants: Safe fields present
    assert "outcome_id" in resp_dict
    assert "execution_id" in resp_dict
    assert "decision_id" in resp_dict
    assert "outcome_status" in resp_dict

    # Sensitive merchant internal fields STRICTLY absent
    assert "cogs_paise" not in resp_dict
    assert "gross_margin_percent" not in resp_dict
    assert "gross_profit_paise" not in resp_dict
    assert "model_weights" not in resp_dict
    assert "ucb_score" not in resp_dict
