"""Integration tests for Phase 8.6 Deterministic Policy Safety Gate Service & API.

Contract: policy-safety/v1
Verifies:
- Service revalidates candidate against fresh DB state.
- Idempotency on (merchant_id, opportunity_id, policy_id).
- Historical safety check retrieval and tenant isolation.
- FastAPI endpoints (POST /validate, GET /{id}).
- Rejection behavior and version validation.
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient

from domain.models import Merchant, Product
from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus
)
from services.safety.schemas import (
    SAFETY_SCHEMA_VERSION,
    PolicySafetyRequest,
    PolicySafetyResult,
    PolicySafetyStatus,
    PolicySafetyFailureCode
)
from services.safety.service import PolicySafetyService
from services.safety.errors import (
    MerchantSafetyIsolationError,
    SafetyCheckNotFoundError,
    IncompatibleSafetyVersionError
)


@pytest.fixture
async def seed_safety_merchants_and_products(db_session):
    m1 = Merchant(
        id="merch_saf_a",
        name="Safety Merchant A",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=8.0,
        target_aov_paise=400000
    )
    m2 = Merchant(
        id="merch_saf_b",
        name="Safety Merchant B",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=8.0,
        target_aov_paise=400000
    )
    db_session.add_all([m1, m2])

    p1 = Product(
        id="prod_saf_01",
        merchant_id="merch_saf_a",
        sku="SKU-SAF-01",
        name="Safety Backpack",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        currency="INR",
        inventory_quantity=20,
        reserved_quantity=2,
        is_active=True
    )
    p2 = Product(
        id="prod_saf_02",
        merchant_id="merch_saf_a",
        sku="SKU-SAF-02",
        name="Safety Packing Cubes",
        category="packing_cubes",
        price_paise=150000,
        cost_paise=75000,
        currency="INR",
        inventory_quantity=30,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add_all([p1, p2])
    await db_session.commit()
    return m1, m2, p1, p2


@pytest.fixture
def base_safety_request():
    return PolicySafetyRequest(
        merchant_id="merch_saf_a",
        opportunity_id="opp_saf_101",
        buyer_context_key="bck_travel_01",
        proposed_policy=PolicyCandidate(
            candidate_id="cand_saf_single",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=["prod_saf_01"],
            bundle_components=[{"product_id": "prod_saf_01", "quantity": 1}],
            validation_status=CandidateValidationStatus.APPROVED,
            rationale="Single product standard"
        ),
        proposed_policy_version="merchant-policy/v1",
        selection_id="sel_test_01",
        intent=BuyerIntent(
            category="travel_backpack",
            budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=600000),
            quantity=1
        )
    )


@pytest.mark.asyncio
async def test_validate_policy_persists_and_returns_admissible(db_session, seed_safety_merchants_and_products, base_safety_request):
    """Verify that validate_policy runs against fresh DB state, persists record, and returns ADMISSIBLE."""
    res = await PolicySafetyService.validate_policy(db_session, base_safety_request)

    assert isinstance(res, PolicySafetyResult)
    assert res.safety_check_id.startswith("safe_")
    assert res.merchant_id == "merch_saf_a"
    assert res.opportunity_id == "opp_saf_101"
    assert res.policy_id == "cand_saf_single"
    assert res.status == PolicySafetyStatus.ADMISSIBLE
    assert len(res.failure_codes) == 0
    assert res.validation_reason == "ADMISSIBLE_ALL_CONSTRAINTS_SATISFIED"
    assert res.recalculated_economics is not None
    assert res.recalculated_economics.net_revenue_paise == 500000
    assert res.recalculated_economics.gross_margin_percent == Decimal("50.00")


@pytest.mark.asyncio
async def test_validate_policy_rejects_violation(db_session, seed_safety_merchants_and_products, base_safety_request):
    """Candidate exceeding discount limit must be REJECTED with DISCOUNT_LIMIT_EXCEEDED."""
    base_safety_request.proposed_policy.incentive = IncentiveProposal(
        incentive_type="discount",
        discount_percent=Decimal("20.00")  # max is 8.00%
    )
    res = await PolicySafetyService.validate_policy(db_session, base_safety_request)

    assert res.status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED in res.failure_codes
    assert res.validation_reason == PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED.value


@pytest.mark.asyncio
async def test_idempotency_same_opportunity_and_policy(db_session, seed_safety_merchants_and_products, base_safety_request):
    """Repeated validation for same (merchant_id, opportunity_id, policy_id) returns identical record."""
    res1 = await PolicySafetyService.validate_policy(db_session, base_safety_request)
    res2 = await PolicySafetyService.validate_policy(db_session, base_safety_request)

    assert res1.safety_check_id == res2.safety_check_id
    assert res1.status == res2.status
    assert res1.validated_at == res2.validated_at


@pytest.mark.asyncio
async def test_get_safety_check_and_tenant_isolation(db_session, seed_safety_merchants_and_products, base_safety_request):
    """Fetch safety check by ID and verify cross-tenant access rejection."""
    res = await PolicySafetyService.validate_policy(db_session, base_safety_request)

    # Valid tenant access
    fetched = await PolicySafetyService.get_safety_check(db_session, res.safety_check_id, merchant_id="merch_saf_a")
    assert fetched.safety_check_id == res.safety_check_id
    assert fetched.merchant_id == "merch_saf_a"

    # Cross-tenant access must raise isolation error
    with pytest.raises(MerchantSafetyIsolationError):
        await PolicySafetyService.get_safety_check(db_session, res.safety_check_id, merchant_id="merch_saf_b")


@pytest.mark.asyncio
async def test_safety_api_endpoints(client: AsyncClient, seed_safety_merchants_and_products, base_safety_request):
    """End-to-end API verification of POST /validate and GET /{id}."""
    payload = base_safety_request.model_dump(mode="json")

    # 1. POST /api/v1/policy-safety/validate
    res_post = await client.post("/api/v1/policy-safety/validate", json=payload)
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["status"] == "ADMISSIBLE"
    check_id = data["safety_check_id"]

    # 2. GET /api/v1/policy-safety/{check_id}
    res_get = await client.get(f"/api/v1/policy-safety/{check_id}?merchant_id=merch_saf_a")
    assert res_get.status_code == 200
    assert res_get.json()["safety_check_id"] == check_id

    # 3. GET with cross-merchant ID must fail with 403
    res_cross = await client.get(f"/api/v1/policy-safety/{check_id}?merchant_id=merch_saf_b")
    assert res_cross.status_code == 403


@pytest.mark.asyncio
async def test_incompatible_version_rejected(db_session, seed_safety_merchants_and_products, base_safety_request):
    """Request with unsupported safety version raises IncompatibleSafetyVersionError."""
    base_safety_request.safety_version = "policy-safety/v99"
    with pytest.raises(IncompatibleSafetyVersionError):
        await PolicySafetyService.validate_policy(db_session, base_safety_request)


@pytest.mark.asyncio
async def test_freshness_and_state_aware_idempotency(db_session, seed_safety_merchants_and_products, base_safety_request):
    """Phase 8.6.1 Refinement:
    1. Unchanged authoritative state returns idempotent cached result for same opportunity.
    2. Changing authoritative state (e.g. inventory 20 -> 0) forces revalidation for same opportunity,
       returning REJECTED and preserving both records in DB without overwriting.
    """
    m1, m2, p1, p2 = seed_safety_merchants_and_products

    # Call 1: Inventory is 20 -> ADMISSIBLE
    res1 = await PolicySafetyService.validate_policy(db_session, base_safety_request)
    assert res1.status == PolicySafetyStatus.ADMISSIBLE
    id_1 = res1.safety_check_id

    # Call 2: Unchanged state -> Returns identical cached result
    res2 = await PolicySafetyService.validate_policy(db_session, base_safety_request)
    assert res2.safety_check_id == id_1
    assert res2.status == PolicySafetyStatus.ADMISSIBLE

    # Now mutate authoritative inventory in DB
    p1.inventory_quantity = 0
    p1.reserved_quantity = 0
    await db_session.commit()

    # Call 3: Same opportunity_id and policy_id, but state changed -> Forces revalidation!
    res3 = await PolicySafetyService.validate_policy(db_session, base_safety_request)
    assert res3.safety_check_id != id_1
    assert res3.status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.INVENTORY_INSUFFICIENT in res3.failure_codes

    # Verify both records exist immutably in DB
    rec1 = await PolicySafetyService.get_safety_check(db_session, id_1, merchant_id="merch_saf_a")
    assert rec1.status == PolicySafetyStatus.ADMISSIBLE
    rec2 = await PolicySafetyService.get_safety_check(db_session, res3.safety_check_id, merchant_id="merch_saf_a")
    assert rec2.status == PolicySafetyStatus.REJECTED

