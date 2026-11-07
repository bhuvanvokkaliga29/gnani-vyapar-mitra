"""Security invariant and boundary integration tests for Phase 5 Execution Gate."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import Merchant, Product
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
async def seed_two_tenants(db_session: AsyncSession):
    """Seed two separate merchants with distinct products."""
    m1 = Merchant(id="merch_alpha", name="Alpha Store", currency="INR")
    m2 = Merchant(id="merch_beta", name="Beta Store", currency="INR")
    db_session.add_all([m1, m2])

    p1 = Product(
        id="prod_alpha_01",
        merchant_id="merch_alpha",
        sku="SKU-A-01",
        name="Alpha Backpack",
        category="backpack",
        price_paise=300000,
        cost_paise=150000,
        inventory_quantity=5,
        reserved_quantity=0,
        is_active=True
    )
    p2 = Product(
        id="prod_beta_01",
        merchant_id="merch_beta",
        sku="SKU-B-01",
        name="Beta Backpack",
        category="backpack",
        price_paise=400000,
        cost_paise=200000,
        inventory_quantity=5,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add_all([p1, p2])
    await db_session.commit()
    return m1, m2, p1, p2


@pytest.mark.asyncio
async def test_cross_tenant_execution_blocked(client: AsyncClient, seed_two_tenants, mock_gate):
    """A proposal for Merchant Alpha cannot be executed against Merchant Beta."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    m1, m2, p1, p2 = seed_two_tenants

    # Candidate belongs to Alpha
    candidate = PolicyCandidate(
        candidate_id="cand_cross_tenant",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        bundle_components=[{"product_id": p1.id, "quantity": 1}],
        rationale="Cross-tenant test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_cross_tenant",
        merchant_id=m1.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    # Caller tries to execute under Merchant Beta!
    payload = {
        "merchant_id": m2.id,  # Beta
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "proposal": proposal.model_dump(mode="json")
    }

    res = await client.post("/api/v1/policy/execute", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "EXECUTION_REJECTED"
    assert "MERCHANT_MISMATCH" in data["authorization"]["rejection_reasons"]
    assert data["order_id"] is None
    assert data["razorpay_order_id"] is None

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_client_amount_tampering_strictly_forbidden(client: AsyncClient, seed_two_tenants):
    """Callers cannot inject custom amounts into the execution request (schema strictly forbids extra fields)."""
    m1, _, p1, _ = seed_two_tenants

    payload = {
        "merchant_id": m1.id,
        "proposal_id": "prop_tamper",
        "candidate_id": "cand_01",
        "amount_paise": 100,  # Smuggled amount!
        "currency": "USD"
    }

    res = await client.post("/api/v1/policy/execute", json=payload)
    assert res.status_code == 422  # Unprocessable Entity rejected by Pydantic extra="forbid"!


@pytest.mark.asyncio
async def test_rejected_candidate_cannot_execute(client: AsyncClient, seed_two_tenants, mock_gate):
    """A candidate marked as REJECTED in proposal cannot be executed."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    m1, _, p1, _ = seed_two_tenants

    candidate = PolicyCandidate(
        candidate_id="cand_rejected",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        bundle_components=[{"product_id": p1.id, "quantity": 1}],
        rationale="Rejected candidate",
        confidence="LOW",
        validation_status=CandidateValidationStatus.REJECTED  # Rejected!
    )
    proposal = PolicyProposal(
        proposal_id="prop_with_rejected",
        merchant_id=m1.id,
        status="REJECTED",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=0,
        rejected_candidates_count=1
    )

    payload = {
        "merchant_id": m1.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "proposal": proposal.model_dump(mode="json")
    }

    res = await client.post("/api/v1/policy/execute", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "EXECUTION_REJECTED"
    assert "INVALID_PROPOSAL_STATUS" in data["authorization"]["rejection_reasons"]
    assert data["order_id"] is None

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_no_offer_strategy_cannot_execute(client: AsyncClient, seed_two_tenants, mock_gate):
    """A proposal resolved to NO_OFFER cannot create an order."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    m1, _, _, _ = seed_two_tenants

    candidate = PolicyCandidate(
        candidate_id="cand_no_offer_exec",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],
        bundle_components=[],
        rationale="No offer",
        confidence="LOW",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_no_offer_exec",
        merchant_id=m1.id,
        status="VALID",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    payload = {
        "merchant_id": m1.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "proposal": proposal.model_dump(mode="json")
    }

    res = await client.post("/api/v1/policy/execute", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "EXECUTION_REJECTED"
    assert "NO_EXECUTABLE_OFFER" in data["authorization"]["rejection_reasons"]
    assert data["order_id"] is None
    assert data["authorized_amount_paise"] == 0

    app.dependency_overrides.pop(get_execution_gate, None)


@pytest.mark.asyncio
async def test_authorization_is_single_use_cannot_reuse_completed_proposal(client: AsyncClient, seed_two_tenants, mock_gate):
    """An ExecutionAuthorization is single-use. Once an order is created, another request cannot execute the same proposal under a different key."""
    app.dependency_overrides[get_execution_gate] = lambda: mock_gate
    m1, _, p1, _ = seed_two_tenants

    candidate = PolicyCandidate(
        candidate_id="cand_single_use",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        bundle_components=[{"product_id": p1.id, "quantity": 1}],
        rationale="Single-use test",
        confidence="HIGH",
        validation_status=CandidateValidationStatus.APPROVED
    )
    proposal = PolicyProposal(
        proposal_id="prop_single_use_01",
        merchant_id=m1.id,
        status="APPROVED_FOR_EVALUATION",
        candidates=[candidate],
        selected_candidate=candidate,
        total_candidates=1,
        valid_candidates_count=1
    )

    # First execution: Succeeds and creates order
    payload_1 = {
        "merchant_id": m1.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "idempotency_key": "attempt_1_key",
        "proposal": proposal.model_dump(mode="json")
    }
    res1 = await client.post("/api/v1/policy/execute", json=payload_1)
    assert res1.status_code == 200
    assert res1.json()["status"] == "ORDER_CREATED"

    # Second execution: Different attempt/key trying to reuse the already-executed proposal
    payload_2 = {
        "merchant_id": m1.id,
        "proposal_id": proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "idempotency_key": "attempt_2_new_key",
        "proposal": proposal.model_dump(mode="json")
    }
    res2 = await client.post("/api/v1/policy/execute", json=payload_2)
    assert res2.status_code == 200
    data2 = res2.json()

    # Must be rejected because proposal has already been executed!
    assert data2["status"] == "EXECUTION_REJECTED"
    assert "EXECUTION_ALREADY_COMPLETED" in data2["authorization"]["rejection_reasons"]
    assert data2["order_id"] is None

    app.dependency_overrides.pop(get_execution_gate, None)

