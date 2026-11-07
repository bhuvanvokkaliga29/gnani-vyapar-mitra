"""Integration tests for Phase 9.4 Trace Reconstruction and Diagnostic Visibility."""

import pytest
from decimal import Decimal
from sqlalchemy import select

from domain.models import (
    Merchant,
    Product,
    Order,
    Payment,
)
from apps.api.core.state_machine import TransactionState
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService
from services.observability.trace import (
    TraceReconstructionService,
    TraceStageStatus,
)
from services.audit.errors import AuditTenantViolationError


@pytest.fixture
async def seed_trace_merchant(db_session):
    """Seed merchant and product for trace reconstruction tests."""
    merchant = Merchant(
        id="merch_trace_alpha",
        name="Trace Alpha Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    product = Product(
        id="prod_trace_01",
        merchant_id=merchant.id,
        sku="SKU-TRACE-01",
        name="Traceable Backpack",
        category="travel_backpack",
        price_paise=350000,
        cost_paise=200000,
        inventory_quantity=50,
        is_active=True,
        attributes={"laptop_size": 15.6}
    )
    db_session.add_all([merchant, product])
    await db_session.commit()
    return merchant, product


@pytest.mark.asyncio
async def test_reconstruct_full_lifecycle_completed_trace(db_session, seed_trace_merchant):
    """Verify trace reconstruction rebuilds all 8 stages of a completed transaction lifecycle."""
    merchant, _ = seed_trace_merchant
    opp_id = "opp_trace_full_01"

    # 1. Decision
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id=opp_id,
        raw_prompt="travel backpack under 4000",
        request_id="req_trace_test_01"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)

    # 2. Execution
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=merchant.id)
    )

    # 3. Transaction Paid
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    db_session.add(Payment(
        id=f"pay_trace_{order.id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured"
    ))
    await db_session.commit()

    # 4. Outcome & Learning
    outcome_resp = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=merchant.id, execution_id=boundary_res.execution_id)
    )

    # 5. Reconstruct Trace
    trace = await TraceReconstructionService.reconstruct_opportunity(
        db=db_session,
        merchant_id=merchant.id,
        opportunity_id=opp_id
    )

    # Invariants
    assert trace.trace_status == TraceStageStatus.COMPLETED.value
    assert trace.merchant_id == merchant.id
    assert trace.opportunity_id == opp_id
    assert trace.request_id == "req_trace_test_01"
    assert trace.decision_id == envelope.decision_id
    assert trace.execution_id == boundary_res.execution_id
    assert trace.order_id == boundary_res.order_id
    assert trace.outcome_id == outcome_resp.outcome_id
    assert trace.evidence_id == outcome_resp.evidence_id
    assert trace.memory_id == outcome_resp.memory_id
    assert trace.applied_observation_id is not None

    # Check all stages present
    expected_stages = [
        "9.1_DECISION",
        "9.2_EXECUTION",
        "PHASE_5_ORDER",
        "PHASE_5_PAYMENT",
        "9.3_OUTCOME",
        "8.1_EVIDENCE",
        "8.3_MEMORY",
        "8.4_MODEL_UPDATE",
    ]
    for stg in expected_stages:
        assert stg in trace.stages_present


@pytest.mark.asyncio
async def test_reconstruct_trace_stopped_at_execution(db_session, seed_trace_merchant):
    """Verify trace reconstruction correctly diagnoses when a decision was never executed."""
    merchant, _ = seed_trace_merchant
    opp_id = "opp_trace_unexecuted_02"

    # Only decide, never execute
    await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=merchant.id, opportunity_id=opp_id, raw_prompt="travel backpack")
    )

    trace = await TraceReconstructionService.reconstruct_opportunity(
        db=db_session,
        merchant_id=merchant.id,
        opportunity_id=opp_id
    )

    assert trace.trace_status == TraceStageStatus.STOPPED_AT_EXECUTION.value
    assert "9.1_DECISION" in trace.stages_present
    assert "9.2_EXECUTION" not in trace.stages_present
    assert trace.stopped_reason is not None


@pytest.mark.asyncio
async def test_reconstruct_trace_cross_tenant_rejected(db_session, seed_trace_merchant):
    """Verify trace reconstruction rejects cross-tenant attempts."""
    merchant, _ = seed_trace_merchant

    with pytest.raises(AuditTenantViolationError):
        await TraceReconstructionService.reconstruct_opportunity(
            db=db_session,
            merchant_id="",
            opportunity_id="opp_any"
        )
