"""Integration tests for Phase 5 Execution Gate and POST /api/v1/policy/execute."""

import pytest
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


@pytest.fixture
def mock_gate():
    mock_rzp = MockRazorpayClient()
    rzp_orders = RazorpayOrderService(client=mock_rzp)
    order_svc = OrderService(razorpay_orders=rzp_orders)
    return ExecutionGate(order_service=order_svc)


@pytest.fixture
async def seed_merchant_and_product(db_session: AsyncSession):
    """Seed test merchant and product into DB."""
    merchant = Merchant(
        id="merch_exec_test",
        name="Execution Test Merchant",
        currency="INR",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=8.0,
        target_aov_paise=400000
    )
    db_session.add(merchant)

    product = Product(
        id="prod_exec_01",
        merchant_id="merch_exec_test",
        sku="SKU-EXEC-01",
        name="Atlas Pro Backpack",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        currency="INR",
        inventory_quantity=10,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add(product)
    await db_session.commit()
    return merchant, product


@pytest.mark.asyncio
async def test_execute_policy_end_to_end_order_created(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product, mock_gate):
    """POST /api/v1/policy/execute successfully revalidates, reserves stock, and creates order."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    merchant, product = seed_merchant_and_product

    candidate = PolicyCandidate(
        candidate_id="cand_exec_01",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Top pick",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_exec_01",
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

    assert data["status"] == "ORDER_CREATED"
    assert data["authorized_amount_paise"] == 500000
    assert data["currency"] == "INR"
    assert data["order_id"] is not None
    assert data["razorpay_order_id"] is not None
    assert len(data["authorization"]["receipt"]) <= 40

    # Verify inventory was atomically reserved
    await db_session.refresh(product)
    assert product.reserved_quantity == 1

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_idempotent_execution_replayed_no_duplicate_order(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product, mock_gate):
    """Submitting the same execution request twice returns the existing order without creating a duplicate."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    merchant, product = seed_merchant_and_product

    candidate = PolicyCandidate(
        candidate_id="cand_exec_idem",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Idempotency test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_exec_idem",
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
        "idempotency_key": "idem_fixed_key_001",
        "proposal": proposal.model_dump(mode="json")
    }

    # Run 1: Creates order
    res1 = await client.post("/api/v1/policy/execute", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_duplicate"] is False
    order_id_1 = data1["order_id"]

    # Run 2: Replays same idempotency key
    res2 = await client.post("/api/v1/policy/execute", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_duplicate"] is True
    assert data2["order_id"] == order_id_1  # Exact same order returned!

    # Inventory reserved only once!
    await db_session.refresh(product)
    assert product.reserved_quantity == 1

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_stale_inventory_rejected_from_execution(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product, mock_gate):
    """If inventory is depleted in fresh state, execution gate rejects with OUT_OF_STOCK."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    merchant, product = seed_merchant_and_product

    # Deplete product stock in DB
    product.inventory_quantity = 0
    await db_session.commit()

    candidate = PolicyCandidate(
        candidate_id="cand_exec_oos",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Stale stock",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_exec_oos",
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

    assert data["status"] == "EXECUTION_REJECTED"
    assert "OUT_OF_STOCK" in data["authorization"]["rejection_reasons"]
    assert data["order_id"] is None
    assert data["razorpay_order_id"] is None
    assert data["authorized_amount_paise"] == 0

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_get_execution_record_audit(client: AsyncClient, db_session: AsyncSession, seed_merchant_and_product, mock_gate):
    """GET /api/v1/policy/executions/{id} retrieves immutable audit details."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    merchant, product = seed_merchant_and_product

    candidate = PolicyCandidate(
        candidate_id="cand_exec_get",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[product.id],
        bundle_components=[{"product_id": product.id, "quantity": 1}],
        rationale="Get test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_exec_get",
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
    exec_id = res.json()["execution_id"]

    # Fetch audit record
    audit_res = await client.get(f"/api/v1/policy/executions/{exec_id}")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["execution_id"] == exec_id
    assert audit_data["authorized_amount_paise"] == 500000

    app.dependency_overrides.pop(get_execution_gate, None)
