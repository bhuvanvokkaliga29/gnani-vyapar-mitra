"""Integration Tests for Phase 9.3 Outcome, Feedback & Recovery Loop.

Contract: outcome-feedback/v1
Tests:
- End-to-end traversal: Canonical Decision (9.1) -> Execution Boundary (9.2) -> Order created -> Payment captured -> Outcome processed (9.3) -> Evidence (8.1) -> Reward (8.2) -> Memory (8.3) -> Model updated (8.4).
- Idempotent re-processing replays cached outcome without duplicate memory or duplicate model updates.
- Failed payment outcome recorded as non-purchase evidence with 0 reward.
- FastAPI endpoints for outcome processing and retrieval.
"""

import pytest
from httpx import AsyncClient
from decimal import Decimal
from datetime import datetime, timezone
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
    PolicyLearningModelState
)
from apps.api.core.state_machine import TransactionState
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.outcome.schemas import (
    OutcomeStatus,
    ProcessingState,
    OutcomeProcessRequest,
    OutcomeProcessResponse
)
from services.outcome.service import OutcomeFeedbackService
from services.learning.model_service import PolicyLearningModelService


@pytest.fixture
async def seed_integration_merchant(db_session):
    """Seed active merchant with valid product catalog and healthy margin constraint."""
    merchant = Merchant(
        id="merch_out_int_01",
        name="Atlas Expedition Gear",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("25.00")
    )
    db_session.add(merchant)

    prod = Product(
        id="prod_out_pack_01",
        merchant_id=merchant.id,
        sku="SKU-OUT-PACK-01",
        name="Atlas Range Backpack",
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
async def test_end_to_end_successful_outcome_learning_loop(db_session, seed_integration_merchant):
    """Full closed-loop pipeline: Decision (9.1) -> Execute (9.2) -> Payment Captured -> Outcome (9.3) -> Evidence (8.1) -> Reward (8.2) -> Memory (8.3) -> Model (8.4)."""
    merchant, prod = seed_integration_merchant

    # 1. Phase 9.1: Canonical Decision
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_out_loop_001",
        raw_prompt="travel backpack under 5000 with 15.6 inch laptop compartment"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    assert envelope.execution_authorized is False

    # 2. Phase 9.2: Runtime Boundary Execution
    exec_req = DecisionExecuteRequest(merchant_id=merchant.id)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=exec_req
    )
    assert boundary_res.boundary_status.value == "EXECUTION_COMPLETED"
    assert boundary_res.order_id is not None

    # Verify initial model state
    model_pre, _ = await PolicyLearningModelService.get_or_create_model(db_session, merchant.id)
    obs_count_pre = model_pre.observation_count

    # 3. Simulate Payment Capture in Phase 5
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value

    payment = Payment(
        id=f"pay_test_{boundary_res.order_id[-12:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured",
        method="upi",
        captured_at=datetime.now(timezone.utc)
    )
    db_session.add(payment)
    await db_session.commit()

    # 4. Phase 9.3: Process Outcome Feedback
    proc_req = OutcomeProcessRequest(
        merchant_id=merchant.id,
        execution_id=boundary_res.execution_id
    )
    outcome_resp = await OutcomeFeedbackService.process_outcome(db_session, proc_req)

    # Invariants: Outcome resolution & closed loop completion
    assert outcome_resp.outcome_status == OutcomeStatus.PAYMENT_SUCCESS
    assert outcome_resp.processing_state == ProcessingState.COMPLETED
    assert outcome_resp.is_terminal is True
    assert outcome_resp.learning_eligible is True
    assert outcome_resp.evidence_id is not None
    assert outcome_resp.memory_id is not None
    assert outcome_resp.reward_contribution_paise is not None
    assert outcome_resp.reward_contribution_paise > 0
    assert outcome_resp.is_duplicate is False

    # 5. Verify Downstream Persistence
    # Phase 8.1 Evidence
    evi_rec = (await db_session.execute(
        select(LearningEvidenceRecord).where(LearningEvidenceRecord.id == outcome_resp.evidence_id)
    )).scalar_one()
    assert evi_rec.learning_eligible is True
    assert evi_rec.outcome_type == "PAYMENT_SUCCESS"

    # Phase 8.3 Memory
    mem_rec = (await db_session.execute(
        select(PolicyMemoryRecord).where(PolicyMemoryRecord.id == outcome_resp.memory_id)
    )).scalar_one()
    assert mem_rec.is_current is True
    assert mem_rec.reward_contribution_paise == outcome_resp.reward_contribution_paise

    # Phase 8.4 Model updated
    model_post, _ = await PolicyLearningModelService.get_or_create_model(db_session, merchant.id)
    assert model_post.observation_count == obs_count_pre + 1


@pytest.mark.asyncio
async def test_idempotent_outcome_reprocessing_exactly_once_learning(db_session, seed_integration_merchant):
    """Repeated outcome processing returns cached response and never applies duplicate reward to model."""
    merchant, prod = seed_integration_merchant

    # 1. Evaluate & Execute
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_out_idemp_001",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=merchant.id)
    )

    # 2. Simulate Payment
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    pmt = Payment(
        id=f"pay_idemp_{boundary_res.order_id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="captured"
    )
    db_session.add(pmt)
    await db_session.commit()

    # 3. First Outcome Processing
    proc_req = OutcomeProcessRequest(merchant_id=merchant.id, execution_id=boundary_res.execution_id)
    res_first = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert res_first.is_duplicate is False

    # Check model observation count
    model_first, _ = await PolicyLearningModelService.get_or_create_model(db_session, merchant.id)
    obs_count_first = model_first.observation_count
    b_first = list(model_first.b)

    # 4. Repeated Outcome Processing (Idempotency Replay)
    res_second = await OutcomeFeedbackService.process_outcome(db_session, proc_req)
    assert res_second.is_duplicate is True
    assert res_second.outcome_id == res_first.outcome_id
    assert res_second.evidence_id == res_first.evidence_id
    assert res_second.memory_id == res_first.memory_id

    # Invariant: EXACTLY-ONCE LEARNING EFFECT (model untouched on replay)
    model_second, _ = await PolicyLearningModelService.get_or_create_model(db_session, merchant.id)
    assert model_second.observation_count == obs_count_first
    assert list(model_second.b) == b_first


@pytest.mark.asyncio
async def test_failed_payment_outcome_recorded_as_zero_reward(db_session, seed_integration_merchant):
    """Payment failure outcome is terminal, learning-eligible, and recorded with 0 reward."""
    merchant, prod = seed_integration_merchant

    # 1. Evaluate & Execute
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_out_fail_001",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=merchant.id)
    )

    # 2. Simulate Payment Failure
    order = (await db_session.execute(select(Order).where(Order.id == boundary_res.order_id))).scalar_one()
    order.status = TransactionState.FAILED.value
    fail_pmt = Payment(
        id=f"pay_fail_{boundary_res.order_id[-10:]}",
        order_id=order.id,
        amount_paise=boundary_res.authorized_amount_paise,
        currency="INR",
        status="failed",
        error_code="BAD_REQUEST_PAYMENT_TIMED_OUT"
    )
    db_session.add(fail_pmt)
    await db_session.commit()

    # 3. Process Outcome
    proc_req = OutcomeProcessRequest(merchant_id=merchant.id, execution_id=boundary_res.execution_id)
    outcome_res = await OutcomeFeedbackService.process_outcome(db_session, proc_req)

    # Invariants
    assert outcome_res.outcome_status == OutcomeStatus.PAYMENT_FAILED
    assert outcome_res.is_terminal is True
    assert outcome_res.learning_eligible is True
    assert outcome_res.reward_contribution_paise == 0


@pytest.mark.asyncio
async def test_fastapi_outcome_endpoints(client: AsyncClient, seed_integration_merchant):
    """FastAPI endpoints POST /process, GET /outcomes/{id}, GET /executions/{id}/outcome work properly."""
    merchant, _ = seed_integration_merchant

    # 1. Create Decision
    dec_post = await client.post(
        "/api/v1/decisions/evaluate",
        json={"merchant_id": merchant.id, "opportunity_id": "opp_api_out_001", "raw_prompt": "travel backpack"}
    )
    dec_id = dec_post.json()["decision_id"]

    # 2. Execute Decision
    exec_post = await client.post(
        f"/api/v1/decisions/{dec_id}/execute",
        json={"merchant_id": merchant.id}
    )
    exec_id = exec_post.json()["execution_id"]

    # 3. Call Process Outcome (Order is currently ORDER_CREATED / unpaid)
    proc_post = await client.post(
        "/api/v1/outcomes/process",
        json={"merchant_id": merchant.id, "execution_id": exec_id}
    )
    assert proc_post.status_code == 200
    proc_data = proc_post.json()
    assert proc_data["outcome_status"] == "ORDER_CREATED"
    assert proc_data["learning_eligible"] is False
    outcome_id = proc_data["outcome_id"]

    # 4. Fetch Outcome by ID
    get_out = await client.get(f"/api/v1/outcomes/{outcome_id}?merchant_id={merchant.id}")
    assert get_out.status_code == 200
    assert get_out.json()["outcome_id"] == outcome_id

    # 5. Fetch Outcome by Execution ID
    get_exec_out = await client.get(f"/api/v1/executions/{exec_id}/outcome?merchant_id={merchant.id}")
    assert get_exec_out.status_code == 200
    assert get_exec_out.json()["outcome_id"] == outcome_id


@pytest.mark.asyncio
async def test_webhook_driven_outcome_progression(db_session, seed_integration_merchant):
    """Authoritative WebhookService automatically resolves outcome to PAYMENT_SUCCESS upon order.paid webhook."""
    import hmac
    import hashlib
    import json
    from services.webhook_service import WebhookService
    from apps.api.core.config import settings

    merchant, prod = seed_integration_merchant

    # 1. Decide & Execute
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id="opp_out_wh_001",
        raw_prompt="travel backpack under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(db_session, dec_req)
    boundary_res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=merchant.id)
    )

    # 2. Simulate Razorpay order.paid Webhook
    rzp_order_id = boundary_res.razorpay_order_id
    payload_dict = {
        "entity": "event",
        "account_id": "acc_test_123",
        "event": "order.paid",
        "contains": ["order", "payment"],
        "payload": {
            "order": {
                "entity": {
                    "id": rzp_order_id,
                    "amount": boundary_res.authorized_amount_paise,
                    "status": "paid"
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_wh_{rzp_order_id[-10:]}",
                    "order_id": rzp_order_id,
                    "amount": boundary_res.authorized_amount_paise,
                    "status": "captured",
                    "method": "upi"
                }
            }
        }
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    wh_service = WebhookService(webhook_secret=secret)
    wh_res = await wh_service.process_webhook(
        raw_body=raw_body,
        signature=sig,
        event_id=f"evt_wh_out_{rzp_order_id[-10:]}",
        db=db_session
    )
    assert wh_res["status"] == "processed"

    # 3. Verify outcome was automatically resolved and closed-loop learning completed
    outcome = await OutcomeFeedbackService.get_outcome_by_execution(
        db=db_session,
        execution_id=boundary_res.execution_id,
        merchant_id=merchant.id
    )
    assert outcome.outcome_status == OutcomeStatus.PAYMENT_SUCCESS
    assert outcome.processing_state == ProcessingState.COMPLETED
    assert outcome.is_terminal is True
    assert outcome.learning_eligible is True
    assert outcome.evidence_id is not None
    assert outcome.memory_id is not None

