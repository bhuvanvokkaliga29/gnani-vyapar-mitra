"""Integration tests for Phase 8.7 Policy Exploration Service & API.

Contract: policy-exploration/v1
Verifies:
- End-to-end exploration decision and database state persistence.
- Phase 8.6 safety gate integration and fallback when exploration is inadmissible.
- Opportunity idempotency: repeated request does not consume budget twice.
- Merchant tenant isolation on retrieval.
- FastAPI endpoints (POST /decide, GET /{id}).
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
from services.selection.schemas import (
    PolicySelectionResult,
    CandidateSelectionScore
)
from services.exploration.schemas import (
    EXPLORATION_SCHEMA_VERSION,
    ExplorationRequest,
    ExplorationDecision,
    ExplorationMode,
    ExplorationReasonCode,
    MerchantExplorationConfig
)
from services.exploration.service import PolicyExplorationService
from services.exploration.errors import (
    MerchantExplorationIsolationError,
    ExplorationDecisionNotFoundError,
    IncompatibleExplorationVersionError
)


@pytest.fixture
async def seed_exploration_db(db_session):
    m1 = Merchant(
        id="merch_exp_a",
        name="Exploration Merchant A",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=15.0,
        target_aov_paise=400000
    )
    m2 = Merchant(
        id="merch_exp_b",
        name="Exploration Merchant B",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=15.0,
        target_aov_paise=400000
    )
    db_session.add_all([m1, m2])

    p1 = Product(
        id="prod_exp_01",
        merchant_id="merch_exp_a",
        sku="SKU-EXP-01",
        name="Exploration Pack",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        currency="INR",
        inventory_quantity=20,
        reserved_quantity=0,
        is_active=True
    )
    p2 = Product(
        id="prod_exp_02",
        merchant_id="merch_exp_a",
        sku="SKU-EXP-02",
        name="Exploration Sleeve",
        category="laptop_sleeve",
        price_paise=150000,
        cost_paise=75000,
        currency="INR",
        inventory_quantity=20,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add_all([p1, p2])
    await db_session.commit()
    return m1, m2, p1, p2


@pytest.fixture
def base_exploration_request():
    cand_exploit = PolicyCandidate(
        candidate_id="c_exploit",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_exp_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Exploit single product"
    )
    cand_alt_unc = PolicyCandidate(
        candidate_id="c_alt_unc",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_exp_01"],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Exploratory candidate with high uncertainty"
    )
    cand_baseline = PolicyCandidate(
        candidate_id="cand_base_no_offer",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Reserve baseline"
    )

    from datetime import datetime, timezone
    selection_res = PolicySelectionResult(
        selection_id="sel_exp_01",
        merchant_id="merch_exp_a",
        opportunity_id="opp_exp_100",
        buyer_context_key="bck_exp",
        selected_policy_id="c_exploit",
        selected_policy_version="merchant-policy/v1",
        baseline_policy_id="cand_base_no_offer",
        selected_predicted_contribution_paise=50000,
        selected_uncertainty=0.10,
        baseline_predicted_contribution_paise=0,
        ranked_candidates=[
            CandidateSelectionScore(
                policy_id="c_exploit",
                predicted_contribution_paise=50000,
                uncertainty=0.10,
                rank=1,
                is_baseline=False,
                selection_eligible=True
            ),
            CandidateSelectionScore(
                policy_id="c_alt_unc",
                predicted_contribution_paise=46000,
                uncertainty=0.45,  # gap = 0.35 >= 0.20
                rank=2,
                is_baseline=False,
                selection_eligible=True
            ),
            CandidateSelectionScore(
                policy_id="cand_base_no_offer",
                predicted_contribution_paise=0,
                uncertainty=0.0,
                rank=3,
                is_baseline=True,
                selection_eligible=True
            )
        ],
        selection_reason="Top predicted contribution",
        selection_timestamp=datetime.now(timezone.utc)
    )

    return ExplorationRequest(
        merchant_id="merch_exp_a",
        opportunity_id="opp_exp_100",
        buyer_context_key="bck_exp",
        intent=BuyerIntent(
            category="travel_backpack",
            budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=600000),
            quantity=1
        ),
        candidates=[cand_exploit, cand_alt_unc, cand_baseline],
        selection_result=selection_res,
        config=MerchantExplorationConfig(min_uncertainty_gap=0.20)
    )


@pytest.mark.asyncio
async def test_decide_exploration_end_to_end_explores(db_session, seed_exploration_db, base_exploration_request):
    """When uncertainty advantage trigger is met and candidate is admissible, mode must be EXPLORE."""
    res = await PolicyExplorationService.decide_exploration(db_session, base_exploration_request)

    assert isinstance(res, ExplorationDecision)
    assert res.mode == ExplorationMode.EXPLORE
    assert res.selected_policy_id == "c_alt_unc"
    assert res.exploit_policy_id == "c_exploit"
    assert res.reason_code == ExplorationReasonCode.EXPLORE_UNCERTAINTY_ADVANTAGE
    assert res.safety_check_reference is not None
    assert res.safety_check_reference.startswith("safe_")
    assert res.exploration_budget_state["opportunities_used"] == 1
    assert res.exploration_budget_state["consecutive_explorations"] == 1


@pytest.mark.asyncio
async def test_decide_exploration_fallback_when_exploration_unadmissible(db_session, seed_exploration_db, base_exploration_request):
    """When exploration candidate fails Phase 8.6, service must fall back to exploit candidate."""
    # Alter c_alt_unc to violate merchant discount limit (e.g. 50% discount when max is 15%)
    for cand in base_exploration_request.candidates:
        if cand.candidate_id == "c_alt_unc":
            cand.incentive = IncentiveProposal(incentive_type="discount", discount_percent=Decimal("50.00"))

    res = await PolicyExplorationService.decide_exploration(db_session, base_exploration_request)

    assert res.mode == ExplorationMode.EXPLOIT
    assert res.selected_policy_id == "c_exploit"
    assert res.reason_code == ExplorationReasonCode.EXPLOIT_FALLBACK_EXPLORATION_UNSAFE
    # Budget must NOT be consumed
    assert res.exploration_budget_state["opportunities_used"] == 0
    assert res.exploration_budget_state["consecutive_explorations"] == 0


@pytest.mark.asyncio
async def test_idempotency_same_opportunity(db_session, seed_exploration_db, base_exploration_request):
    """Calling decide_exploration repeatedly for same opportunity returns identical decision without double-spending."""
    res1 = await PolicyExplorationService.decide_exploration(db_session, base_exploration_request)
    res2 = await PolicyExplorationService.decide_exploration(db_session, base_exploration_request)

    assert res1.decision_id == res2.decision_id
    assert res1.mode == res2.mode
    assert res1.selected_policy_id == res2.selected_policy_id
    assert res1.exploration_budget_state["opportunities_used"] == res2.exploration_budget_state["opportunities_used"] == 1


@pytest.mark.asyncio
async def test_get_decision_and_tenant_isolation(db_session, seed_exploration_db, base_exploration_request):
    """Fetching decision enforces strict merchant tenant isolation."""
    res = await PolicyExplorationService.decide_exploration(db_session, base_exploration_request)

    # Valid tenant retrieval
    fetched = await PolicyExplorationService.get_decision(db_session, res.decision_id, merchant_id="merch_exp_a")
    assert fetched.decision_id == res.decision_id
    assert fetched.merchant_id == "merch_exp_a"

    # Cross-tenant retrieval raises isolation error
    with pytest.raises(MerchantExplorationIsolationError):
        await PolicyExplorationService.get_decision(db_session, res.decision_id, merchant_id="merch_exp_b")


@pytest.mark.asyncio
async def test_fastapi_endpoints(client: AsyncClient, seed_exploration_db, base_exploration_request):
    """Verify HTTP POST /decide and GET /{decision_id} endpoints."""
    payload = base_exploration_request.model_dump(mode="json")

    # 1. POST /api/v1/policy-exploration/decide
    res_post = await client.post("/api/v1/policy-exploration/decide", json=payload)
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["mode"] == "EXPLORE"
    decision_id = data["decision_id"]

    # 2. GET /api/v1/policy-exploration/{decision_id}
    res_get = await client.get(f"/api/v1/policy-exploration/{decision_id}?merchant_id=merch_exp_a")
    assert res_get.status_code == 200
    assert res_get.json()["decision_id"] == decision_id

    # 3. GET with cross-merchant ID must fail with 403
    res_cross = await client.get(f"/api/v1/policy-exploration/{decision_id}?merchant_id=merch_exp_b")
    assert res_cross.status_code == 403


@pytest.mark.asyncio
async def test_incompatible_version_rejected(db_session, seed_exploration_db, base_exploration_request):
    """Request with unsupported exploration version raises IncompatibleExplorationVersionError."""
    base_exploration_request.exploration_version = "policy-exploration/v99"
    with pytest.raises(IncompatibleExplorationVersionError):
        await PolicyExplorationService.decide_exploration(db_session, base_exploration_request)
