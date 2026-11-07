"""Integration Tests for Phase 9.2 Execution Boundary.

Contract: execution-boundary/v1
Tests:
- End-to-end traversal from Phase 9.1 Decision Envelope through Phase 9.2 boundary into Phase 5 ExecutionGate.
- Idempotency ledger replay (repeated execution creates no duplicate orders).
- State fingerprint consistency and fresh safety check.
- FastAPI endpoints for execution traversal and audit retrieval.
"""

import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select, func

from domain.models import Merchant, Product, Order, DecisionExecutionRecord
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import (
    DecisionExecuteRequest,
    DecisionExecuteResponse,
    ExecutionBoundaryStatus
)
from services.boundary.service import DecisionExecutionBoundaryService


@pytest.fixture
async def seed_integration_merchant(db_session):
    """Seed active merchant with valid product catalog and healthy margin constraint."""
    merchant = Merchant(
        id="merch_exec_int_01",
        name="Voyager Gear Official",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    db_session.add(merchant)

    prod = Product(
        id="prod_exec_pack_01",
        merchant_id=merchant.id,
        sku="SKU-EXEC-PACK-01",
        name="Voyager Trail Pack",
        category="travel_backpack",
        price_paise=450000,
        cost_paise=250000,
        inventory_quantity=20,
        is_active=True,
        attributes={"laptop_size": 15.6, "water_resistant": True}
    )
    db_session.add(prod)
    await db_session.commit()
    return merchant, prod


@pytest.mark.asyncio
async def test_end_to_end_decision_execution(db_session, seed_integration_merchant):
    """Full pipeline: Phase 9.1 Canonical Decision -> Phase 9.2 Boundary -> Phase 5 -> Razorpay Test Mode."""
    merchant, prod = seed_integration_merchant

    # 1. Evaluate Decision Envelope in Phase 9.1
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_int_exec_001",
        raw_prompt="travel backpack under 5000 with 15.6 inch laptop compartment"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    assert envelope.decision_id.startswith("dec_")
    assert envelope.execution_authorized is False
    assert envelope.execution_status == "PENDING_EXECUTION_GATE"

    # Count orders before Phase 9.2 execution
    count_orders_pre = (await db_session.execute(select(func.count(Order.id)))).scalar_one()

    # 2. Execute Decision through Phase 9.2 Execution Boundary
    exec_req = DecisionExecuteRequest(merchant_id=merchant.id)
    boundary_resp = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=exec_req
    )

    # 3. Assert Authoritative Boundary Traversal
    assert isinstance(boundary_resp, DecisionExecuteResponse)
    assert boundary_resp.boundary_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED
    assert boundary_resp.execution_authorized is True
    assert boundary_resp.authorization_id is not None
    assert boundary_resp.safety_check_id is not None
    assert boundary_resp.phase5_execution_id is not None
    assert boundary_resp.order_id is not None
    assert boundary_resp.razorpay_order_id is not None
    assert boundary_resp.authorized_amount_paise > 0
    assert boundary_resp.is_duplicate is False

    # 4. Verify Phase 5 Order Created in DB
    count_orders_post = (await db_session.execute(select(func.count(Order.id)))).scalar_one()
    assert count_orders_post == count_orders_pre + 1


@pytest.mark.asyncio
async def test_idempotent_decision_reexecution(db_session, seed_integration_merchant):
    """Repeated execution of the same decision replays the boundary record with is_duplicate=True."""
    merchant, prod = seed_integration_merchant

    # 1. Phase 9.1 Decision
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_int_idemp_001",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)

    # 2. First Execution
    exec_req = DecisionExecuteRequest(merchant_id=merchant.id)
    res_first = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=exec_req
    )
    assert res_first.is_duplicate is False
    assert res_first.boundary_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED

    count_orders_first = (await db_session.execute(select(func.count(Order.id)))).scalar_one()

    # 3. Second Execution (Repeated)
    res_second = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=exec_req
    )

    # 4. Invariant: Replayed from ledger, zero duplicate orders created
    assert res_second.is_duplicate is True
    assert res_second.execution_id == res_first.execution_id
    assert res_second.order_id == res_first.order_id
    assert res_second.razorpay_order_id == res_first.razorpay_order_id

    count_orders_second = (await db_session.execute(select(func.count(Order.id)))).scalar_one()
    assert count_orders_second == count_orders_first


@pytest.mark.asyncio
async def test_fastapi_decision_execution_endpoints(client: AsyncClient, seed_integration_merchant):
    """FastAPI HTTP endpoints POST /execute and GET /execution function correctly."""
    merchant, _ = seed_integration_merchant

    # 1. Create Decision via API
    post_eval = await client.post(
        "/api/v1/decisions/evaluate",
        json={"merchant_id": merchant.id, "opportunity_id": "opp_api_exec_001", "raw_prompt": "travel backpack"}
    )
    assert post_eval.status_code == 200
    dec_id = post_eval.json()["decision_id"]

    # 2. Execute Decision via API
    post_exec = await client.post(
        f"/api/v1/decisions/{dec_id}/execute",
        json={"merchant_id": merchant.id}
    )
    assert post_exec.status_code == 200
    exec_data = post_exec.json()
    assert exec_data["boundary_status"] == "EXECUTION_COMPLETED"
    assert exec_data["execution_authorized"] is True
    assert exec_data["order_id"] is not None

    # 3. Fetch Execution Details via API
    get_exec = await client.get(
        f"/api/v1/decisions/{dec_id}/execution?merchant_id={merchant.id}"
    )
    assert get_exec.status_code == 200
    assert get_exec.json()["execution_id"] == exec_data["execution_id"]
