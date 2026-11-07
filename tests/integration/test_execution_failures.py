"""Failure injection and webhook integration tests for Phase 5 Execution Gate."""

import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import Merchant, Product, ExecutionRecord
from services.policy.schemas import PolicyProposal, PolicyCandidate, StrategyType, CandidateValidationStatus
from services.order_service import OrderService
from services.razorpay.orders import RazorpayOrderService
from apps.api.routers.execution import get_execution_gate
from apps.api.main import app
from tests.conftest import MockRazorpayClient
from services.execution.gate import ExecutionGate
from services.execution.schemas import PolicyExecuteRequest
from apps.api.core.config import settings


class FailingRazorpayClient(MockRazorpayClient):
    """Mock client that deliberately raises on order creation."""
    async def request(self, method: str, path: str, json_data=None, params=None):
        if method == "POST" and path == "orders":
            raise Exception("Simulated upstream provider outage")
        return await super().request(method, path, json_data, params)


@pytest.fixture
def failing_gate():
    failing_rzp = FailingRazorpayClient()
    rzp_orders = RazorpayOrderService(client=failing_rzp)
    order_svc = OrderService(razorpay_orders=rzp_orders)
    return ExecutionGate(order_service=order_svc)


@pytest.fixture
async def seed_merchant_and_product(db_session: AsyncSession):
    merchant = Merchant(id="merch_fail_test", name="Fail Merchant", currency="INR")
    product = Product(
        id="prod_fail_01",
        merchant_id="merch_fail_test",
        sku="SKU-FAIL-01",
        name="Test Item",
        category="backpack",
        price_paise=200000,
        cost_paise=100000,
        inventory_quantity=2,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add_all([merchant, product])
    await db_session.commit()
    return merchant, product


@pytest.mark.asyncio
async def test_provider_outage_releases_inventory_safely(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product, failing_gate):
    """When Razorpay order creation fails, inventory reservation is safely rolled back."""
    app.dependency_overrides[get_execution_gate] = lambda: failing_gate
    merchant, product = seed_merchant_and_product

    candidate = PolicyCandidate(
        candidate_id="cand_fail_test",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Failure test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_fail_test",
        merchant_id=merchant.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    payload = {
        "merchant_id": merchant.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "proposal": proposal.model_dump(mode="json")
    }

    res = await client.post("/api/v1/policy/execute", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ORDER_CREATE_FAILED"
    assert data["order_id"] is None

    # CRITICAL INVARIANT: Reserved stock must be released back!
    await db_session.refresh(product)
    assert product.reserved_quantity == 0

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_webhook_payment_captured_handoff(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product):
    """Razorpay payment.captured webhook safely updates order state to PAID."""
    merchant, product = seed_merchant_and_product

    # Create mock gate
    mock_rzp = MockRazorpayClient()
    rzp_orders = RazorpayOrderService(client=mock_rzp)
    order_svc = OrderService(razorpay_orders=rzp_orders)
    gate = ExecutionGate(order_service=order_svc)
    app.dependency_overrides[get_execution_gate] = lambda: gate

    candidate = PolicyCandidate(
        candidate_id="cand_webhook_test",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Webhook test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_webhook_test",
        merchant_id=merchant.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    payload = {
        "merchant_id": merchant.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "proposal": proposal.model_dump(mode="json")
    }

    exec_res = await client.post("/api/v1/policy/execute", json=payload)
    exec_data = exec_res.json()
    rzp_order_id = exec_data["razorpay_order_id"]
    internal_order_id = exec_data["order_id"]
    assert rzp_order_id is not None

    # Now deliver Razorpay payment.captured webhook
    webhook_payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_hook_01",
                    "order_id": rzp_order_id,
                    "amount": 200000,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi"
                }
            }
        },
        "created_at": 1725364800
    }
    body_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    headers = {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": "evt_hook_test_001",
        "Content-Type": "application/json"
    }

    wh_res = await client.post("/webhooks/razorpay", content=body_bytes, headers=headers)
    assert wh_res.status_code == 200

    # Verify order state is now PAID
    order_res = await client.get(f"/api/v1/orders/{internal_order_id}")
    assert order_res.status_code == 200
    assert order_res.json()["status"] == "PAID"

    # Verify inventory was committed/settled
    await db_session.refresh(product)
    assert product.inventory_quantity == 1
    assert product.reserved_quantity == 0

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_payment_failed_webhook_releases_reserved_inventory(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product):
    """When a payment.failed webhook arrives, reserved inventory is released back to available."""
    merchant, product = seed_merchant_and_product

    mock_rzp = MockRazorpayClient()
    rzp_orders = RazorpayOrderService(client=mock_rzp)
    order_svc = OrderService(razorpay_orders=rzp_orders)
    gate = ExecutionGate(order_service=order_svc)
    app.dependency_overrides[get_execution_gate] = lambda: gate

    candidate = PolicyCandidate(
        candidate_id="cand_fail_hook_test",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Fail hook test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_fail_hook_test",
        merchant_id=merchant.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    payload = {
        "merchant_id": merchant.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "proposal": proposal.model_dump(mode="json")
    }

    exec_res = await client.post("/api/v1/policy/execute", json=payload)
    exec_data = exec_res.json()
    rzp_order_id = exec_data["razorpay_order_id"]

    await db_session.refresh(product)
    assert product.reserved_quantity == 1

    # Send payment.failed webhook
    webhook_payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_failed_001",
                    "order_id": rzp_order_id,
                    "amount": 200000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR"
                }
            }
        },
        "created_at": 1725364800
    }
    body_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    headers = {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": "evt_hook_fail_001",
        "Content-Type": "application/json"
    }

    wh_res = await client.post("/webhooks/razorpay", content=body_bytes, headers=headers)
    assert wh_res.status_code == 200

    # CRITICAL INVARIANT: Reserved inventory must be released back!
    await db_session.refresh(product)
    assert product.reserved_quantity == 0
    assert product.inventory_quantity == 2

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_expire_execution_releases_reserved_inventory(db_session: AsyncSession, seed_merchant_and_product):
    """Calling expire_or_cancel_execution releases reserved inventory."""
    merchant, product = seed_merchant_and_product

    mock_rzp = MockRazorpayClient()
    rzp_orders = RazorpayOrderService(client=mock_rzp)
    order_svc = OrderService(razorpay_orders=rzp_orders)
    gate = ExecutionGate(order_service=order_svc)

    candidate = PolicyCandidate(
        candidate_id="cand_expire_test",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Expire test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_expire_test",
        merchant_id=merchant.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    req = PolicyExecuteRequest(
        merchant_id=merchant.id,
        proposal_id=proposal.proposal_id,
        candidate_id=candidate.candidate_id,
        proposal=proposal
    )
    resp = await gate.execute_policy(db_session, req)
    assert resp.status.value == "ORDER_CREATED"

    await db_session.refresh(product)
    assert product.reserved_quantity == 1

    # Now expire execution
    expired_rec = await gate.expire_or_cancel_execution(db_session, resp.execution_id)
    assert expired_rec.status == "EXPIRED"

    await db_session.refresh(product)
    assert product.reserved_quantity == 0


@pytest.mark.asyncio
async def test_real_razorpay_test_mode_order_creation_verified(db_session: AsyncSession, seed_merchant_and_product):
    """Verify end-to-end execution against actual Razorpay Test Mode API using real test credentials."""
    from services.razorpay.client import RazorpayClient

    # Check that real test keys are configured
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_ID.startswith("rzp_test_"):
        pytest.skip("Razorpay Test Mode credentials not configured")

    merchant, product = seed_merchant_and_product
    real_client = RazorpayClient(key_id=settings.RAZORPAY_KEY_ID, key_secret=settings.RAZORPAY_KEY_SECRET)
    rzp_orders = RazorpayOrderService(client=real_client)
    order_svc = OrderService(razorpay_orders=rzp_orders)
    gate = ExecutionGate(order_service=order_svc)

    candidate = PolicyCandidate(
        candidate_id="cand_real_rzp_test",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Real test mode order verification",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_real_rzp_test",
        merchant_id=merchant.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    req = PolicyExecuteRequest(
        merchant_id=merchant.id,
        proposal_id=proposal.proposal_id,
        candidate_id=candidate.candidate_id,
        proposal=proposal
    )
    resp = await gate.execute_policy(db_session, req)

    # Assert real Razorpay Test Mode order was created and verified
    assert resp.status.value == "ORDER_CREATED"
    assert resp.razorpay_order_id is not None
    assert resp.razorpay_order_id.startswith("order_")
    assert resp.authorized_amount_paise == product.price_paise
    assert len(resp.authorization.receipt) <= 40

