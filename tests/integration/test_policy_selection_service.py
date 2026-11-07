"""Integration tests for Phase 8.5 Deterministic Learned Candidate Selection Service & API.

Contract: policy-selection/v1
Verifies:
- Service selection and database persistence.
- Opportunity idempotency.
- Historical selection retrieval and tenant isolation.
- FastAPI endpoints (POST /select, GET /{id}).
"""

import pytest
from decimal import Decimal
from domain.models import Merchant
from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus
)
from services.selection.schemas import PolicySelectionRequest, PolicySelectionResult
from services.selection.service import PolicySelectionService
from services.selection.errors import (
    SelectionNotFoundError,
    MerchantSelectionIsolationError,
    IncompatibleSelectionVersionError
)


@pytest.fixture
async def seed_selection_merchants(db_session):
    m1 = Merchant(id="merch_sel_a", name="Selection Merchant A", currency="INR", status="ACTIVE")
    m2 = Merchant(id="merch_sel_b", name="Selection Merchant B", currency="INR", status="ACTIVE")
    db_session.add_all([m1, m2])
    await db_session.commit()
    return m1, m2


@pytest.fixture
def base_request():
    return PolicySelectionRequest(
        merchant_id="merch_sel_a",
        opportunity_id="opp_sel_001",
        buyer_context_key="bck_travel_mid",
        intent=BuyerIntent(
            category="backpack",
            budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=500000),
            quantity=1
        ),
        candidates=[
            PolicyCandidate(
                candidate_id="cand_single",
                strategy_type=StrategyType.SINGLE_PRODUCT,
                product_ids=["prod_1"],
                validation_status=CandidateValidationStatus.APPROVED,
                rationale="Single product standard"
            ),
            PolicyCandidate(
                candidate_id="cand_bundle",
                strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
                product_ids=["prod_1", "prod_2"],
                bundle_components=[{"product_id": "prod_1"}, {"product_id": "prod_2"}],
                validation_status=CandidateValidationStatus.APPROVED,
                rationale="Complementary bundle"
            )
        ]
    )


@pytest.mark.asyncio
async def test_select_policy_persists_and_returns_valid_result(db_session, seed_selection_merchants, base_request):
    """Verify that selection executes, persists record, and returns complete typed result."""
    result = await PolicySelectionService.select_policy(db_session, base_request)

    assert isinstance(result, PolicySelectionResult)
    assert result.merchant_id == "merch_sel_a"
    assert result.opportunity_id == "opp_sel_001"
    assert result.selection_id.startswith("sel_")
    assert result.selection_version == "policy-selection/v1"
    assert len(result.ranked_candidates) >= 3  # 2 candidates + 1 injected baseline
    assert result.selected_policy_id is not None
    assert result.baseline_policy_id is not None
    assert result.selection_reason in [
        "HIGHEST_PREDICTED_CONTRIBUTION",
        "NO_OFFER_BASELINE_DOMINATES",
        "NO_VALID_POSITIVE_OFFER",
        "DETERMINISTIC_TIE_BREAK"
    ]


@pytest.mark.asyncio
async def test_idempotency_same_merchant_and_opportunity(db_session, seed_selection_merchants, base_request):
    """Repeated selection requests with same (merchant_id, opportunity_id) must return exact same record."""
    res1 = await PolicySelectionService.select_policy(db_session, base_request)
    res2 = await PolicySelectionService.select_policy(db_session, base_request)

    assert res1.selection_id == res2.selection_id
    assert res1.selected_policy_id == res2.selected_policy_id
    assert res1.selection_timestamp == res2.selection_timestamp
    assert res1.ranked_candidates == res2.ranked_candidates


@pytest.mark.asyncio
async def test_get_selection_by_id(db_session, seed_selection_merchants, base_request):
    """Retrieve historical selection by ID."""
    res = await PolicySelectionService.select_policy(db_session, base_request)
    fetched = await PolicySelectionService.get_selection(db_session, res.selection_id, merchant_id="merch_sel_a")

    assert fetched.selection_id == res.selection_id
    assert fetched.opportunity_id == res.opportunity_id
    assert fetched.selected_policy_id == res.selected_policy_id


@pytest.mark.asyncio
async def test_merchant_isolation_on_retrieval(db_session, seed_selection_merchants, base_request):
    """Attempting to access Merchant A's selection with Merchant B's ID must raise isolation error."""
    res = await PolicySelectionService.select_policy(db_session, base_request)

    with pytest.raises(MerchantSelectionIsolationError):
        await PolicySelectionService.get_selection(db_session, res.selection_id, merchant_id="merch_sel_b")


@pytest.mark.asyncio
async def test_selection_api_endpoints(client, seed_selection_merchants, base_request):
    """End-to-end API verification of POST /select and GET /{id}."""
    payload = base_request.model_dump()

    # 1. POST /api/v1/policy-selection/select
    response = await client.post("/api/v1/policy-selection/select", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_id"] == "merch_sel_a"
    assert data["selection_version"] == "policy-selection/v1"
    selection_id = data["selection_id"]

    # 2. GET /api/v1/policy-selection/{selection_id}
    res_get = await client.get(f"/api/v1/policy-selection/{selection_id}?merchant_id=merch_sel_a")
    assert res_get.status_code == 200
    assert res_get.json()["selection_id"] == selection_id

    # 3. GET with cross-merchant ID must fail with 403
    res_cross = await client.get(f"/api/v1/policy-selection/{selection_id}?merchant_id=merch_sel_b")
    assert res_cross.status_code == 403
