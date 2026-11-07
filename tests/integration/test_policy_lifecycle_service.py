"""Integration tests for Phase 8.8 Policy Lifecycle & Promotion Service.

Contracts:
- policy-lifecycle/v1
- promotion-policy/v1

Verifies:
- End-to-end evidence-gated promotion transaction.
- Single active policy invariant (exactly one active policy per merchant).
- Fresh Phase 8.6 safety check integration (rejects unsafe candidate even if memory evidence is positive).
- Optimistic concurrency protection (rejects on predecessor mismatch).
- Idempotency on repeated promotion requests.
- Rollback to historical versions with fresh Phase 8.6 safety check.
- Rejection of rollback if historical policy is currently unsafe.
- FastAPI lifecycle endpoints.
"""

from decimal import Decimal
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from domain.models import (
    Merchant,
    Product,
    PolicyMemoryRecord,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    PolicyLifecycleAuditRecord
)
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus
)
from services.lifecycle.schemas import (
    LIFECYCLE_SCHEMA_VERSION,
    PROMOTION_CONFIG_VERSION,
    PolicyLifecycleState,
    PromotionStatus,
    PromotionFailureCode,
    PromotionPolicyConfig,
    PolicyPromotionRequest,
    PolicyPromotionResult,
    PolicyRollbackRequest,
    PolicyRollbackResult
)
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.errors import (
    IncompatibleLifecycleVersionError,
    PolicyVersionNotFoundError,
    ActivePolicyConflictError
)


@pytest.fixture
async def seed_lifecycle_db(db_session):
    """Seed merchant and products for lifecycle tests."""
    m1 = Merchant(
        id="merch_lcyc_a",
        name="Lifecycle Merchant A",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=15.0,
        target_aov_paise=400000
    )
    p1 = Product(
        id="prod_lcyc_1",
        merchant_id=m1.id,
        name="Travel Backpack Pro",
        description="Durable lightweight backpack",
        sku="SKU-BP-001",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=300000,  # 40% margin at full price
        inventory_quantity=20,
        is_active=True
    )
    db_session.add_all([m1, p1])
    await db_session.commit()
    await db_session.refresh(m1)
    await db_session.refresh(p1)

    # Seed 25 historical memory records for candidate policy (cand_promo_1) with positive contribution
    records = []
    for i in range(25):
        records.append(PolicyMemoryRecord(
            id=f"mem_cand_{i}",
            merchant_id=m1.id,
            opportunity_id=f"opp_cand_{i}",
            buyer_context_key="ctx_lcyc",
            scenario_id="scen_lcyc",
            policy_id="cand_promo_1",
            policy_version="merchant-policy/v1",
            experiment_id="exp_lcyc_1",
            experiment_version="policy-experiment/v1",
            variant="TREATMENT",
            evidence_id=f"evi_cand_{i}",
            evidence_source="SIMULATED",
            outcome_type="TEST_MODE_COMPLETED",
            learning_eligible=True,
            reward_id=f"rew_cand_{i}",
            reward_version="merchant-reward/v1",
            formula_version="contribution-formula/v1",
            reward_state="FINAL",
            is_admissible=True,
            is_safety_violation=False,
            is_current=True,
            reward_contribution_paise=55000,  # +₹550 per shopper
            observed_at=datetime.now(timezone.utc),
            idempotency_key=f"idemp_cand_{i}"
        ))

    # Seed 25 baseline memory records
    for i in range(25):
        records.append(PolicyMemoryRecord(
            id=f"mem_base_{i}",
            merchant_id=m1.id,
            opportunity_id=f"opp_base_{i}",
            buyer_context_key="ctx_lcyc",
            scenario_id="scen_lcyc",
            policy_id="cand_base_no_offer",
            policy_version="merchant-policy/v1",
            experiment_id="exp_lcyc_1",
            experiment_version="policy-experiment/v1",
            variant="CONTROL",
            evidence_id=f"evi_base_{i}",
            evidence_source="SIMULATED",
            outcome_type="TEST_MODE_COMPLETED",
            learning_eligible=True,
            reward_id=f"rew_base_{i}",
            reward_version="merchant-reward/v1",
            formula_version="contribution-formula/v1",
            reward_state="FINAL",
            is_admissible=True,
            is_safety_violation=False,
            is_current=True,
            reward_contribution_paise=30000,  # +₹300 per shopper
            observed_at=datetime.now(timezone.utc),
            idempotency_key=f"idemp_base_{i}"
        ))

    db_session.add_all(records)
    await db_session.commit()
    return m1, p1


@pytest.mark.asyncio
async def test_end_to_end_policy_promotion_transaction(db_session, seed_lifecycle_db):
    """End-to-end evidence-gated promotion promotes candidate policy and enforces single active invariant."""
    m1, p1 = seed_lifecycle_db

    # Valid candidate with 5% discount (margin = (5000 - 250 - 3000) / 4750 = 36.8% > 25% min margin)
    cand = PolicyCandidate(
        candidate_id="cand_promo_1",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=[p1.id],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("5.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Top performing discount policy"
    )

    req = PolicyPromotionRequest(
        merchant_id=m1.id,
        candidate_policy_id="cand_promo_1",
        candidate_policy=cand,
        reason="Demonstrated +₹550 contribution vs +₹300 baseline across 25 opportunities",
        config=PromotionPolicyConfig(min_learning_opportunities=20, min_positive_contribution_paise=1)
    )

    result = await PolicyLifecycleService.promote_policy(db_session, req)
    assert result.promotion_status == PromotionStatus.PROMOTED
    assert result.resulting_active_policy_id == "cand_promo_1"
    assert result.failure_codes == []
    assert result.safety_check_reference is not None

    # Verify single active policy in database
    active_stmt = select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == m1.id)
    active_row = (await db_session.execute(active_stmt)).scalar_one()
    assert active_row.policy_id == "cand_promo_1"

    # Verify version record state is ACTIVE
    ver_stmt = select(MerchantPolicyVersionRecord).where(
        MerchantPolicyVersionRecord.merchant_id == m1.id,
        MerchantPolicyVersionRecord.policy_id == "cand_promo_1"
    )
    ver_row = (await db_session.execute(ver_stmt)).scalar_one()
    assert ver_row.lifecycle_status == PolicyLifecycleState.ACTIVE.value


@pytest.mark.asyncio
async def test_promotion_rejected_when_safety_gate_fails(db_session, seed_lifecycle_db):
    """Even with positive evidence, candidate violating Phase 8.6 commercial safety is rejected."""
    m1, p1 = seed_lifecycle_db

    # Candidate with 25% discount (exceeds merchant 15% maximum discount limit)
    cand_unsafe = PolicyCandidate(
        candidate_id="cand_promo_1",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=[p1.id],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("25.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Aggressive discount policy"
    )

    req = PolicyPromotionRequest(
        merchant_id=m1.id,
        candidate_policy_id="cand_promo_1",
        candidate_policy=cand_unsafe,
        reason="Test safety rejection",
        config=PromotionPolicyConfig(min_learning_opportunities=20)
    )

    result = await PolicyLifecycleService.promote_policy(db_session, req)
    assert result.promotion_status == PromotionStatus.SAFETY_REJECTED
    assert PromotionFailureCode.SAFETY_GATE_REJECTED in result.failure_codes

    # Verify active policy remained untouched (still baseline)
    active_res = await PolicyLifecycleService.get_active_policy(db_session, m1.id)
    assert active_res.policy_id != "cand_promo_1"


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict_on_predecessor_mismatch(db_session, seed_lifecycle_db):
    """Promotion expecting predecessor X fails with CONFLICT if current active policy is Y."""
    m1, p1 = seed_lifecycle_db

    cand = PolicyCandidate(
        candidate_id="cand_promo_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Product policy"
    )

    req = PolicyPromotionRequest(
        merchant_id=m1.id,
        candidate_policy_id="cand_promo_1",
        candidate_policy=cand,
        expected_previous_policy_id="non_existent_policy_predecessor",
        reason="Testing concurrency mismatch"
    )

    result = await PolicyLifecycleService.promote_policy(db_session, req)
    assert result.promotion_status == PromotionStatus.CONFLICT
    assert PromotionFailureCode.PREDECESSOR_MISMATCH in result.failure_codes


@pytest.mark.asyncio
async def test_idempotency_repeated_promotion_request(db_session, seed_lifecycle_db):
    """Repeated promotion request returns cached promotion result without creating duplicate state."""
    m1, p1 = seed_lifecycle_db

    cand = PolicyCandidate(
        candidate_id="cand_promo_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Product policy"
    )

    req = PolicyPromotionRequest(
        merchant_id=m1.id,
        candidate_policy_id="cand_promo_1",
        candidate_policy=cand,
        reason="Idempotency test",
        config=PromotionPolicyConfig(min_learning_opportunities=20)
    )

    res1 = await PolicyLifecycleService.promote_policy(db_session, req)
    assert res1.promotion_status == PromotionStatus.PROMOTED

    res2 = await PolicyLifecycleService.promote_policy(db_session, req)
    assert res2.promotion_status == PromotionStatus.PROMOTED
    assert res1.promotion_id == res2.promotion_id


@pytest.mark.asyncio
async def test_policy_rollback_to_historical_version(db_session, seed_lifecycle_db):
    """Rollback restores historical version to ACTIVE and sets replaced policy to ROLLED_BACK."""
    m1, p1 = seed_lifecycle_db

    # 1. Promote Policy A (cand_promo_1)
    cand_a = PolicyCandidate(
        candidate_id="cand_promo_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Policy A"
    )
    req_a = PolicyPromotionRequest(merchant_id=m1.id, candidate_policy_id="cand_promo_1", candidate_policy=cand_a, reason="Promote A")
    res_a = await PolicyLifecycleService.promote_policy(db_session, req_a)
    assert res_a.promotion_status == PromotionStatus.PROMOTED

    # 2. Seed memory for Policy B (cand_promo_2) and promote it
    for i in range(25):
        db_session.add(PolicyMemoryRecord(
            id=f"mem_cand2_{i}", merchant_id=m1.id, opportunity_id=f"opp_c2_{i}", buyer_context_key="ctx_lcyc",
            scenario_id="scen_lcyc", policy_id="cand_promo_2", policy_version="merchant-policy/v1", experiment_id="exp_lcyc_1",
            variant="TREATMENT", evidence_id=f"evi_c2_{i}", evidence_source="SIMULATED", outcome_type="TEST_MODE_COMPLETED",
            learning_eligible=True, reward_id=f"rew_c2_{i}", reward_version="merchant-reward/v1", formula_version="contribution-formula/v1",
            reward_state="FINAL", is_admissible=True, is_safety_violation=False, is_current=True, reward_contribution_paise=60000,
            observed_at=datetime.now(timezone.utc), idempotency_key=f"idemp_c2_{i}"
        ))
    await db_session.commit()

    cand_b = PolicyCandidate(
        candidate_id="cand_promo_2",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=[p1.id],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("2.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Policy B"
    )
    req_b = PolicyPromotionRequest(merchant_id=m1.id, candidate_policy_id="cand_promo_2", candidate_policy=cand_b, reason="Promote B")
    res_b = await PolicyLifecycleService.promote_policy(db_session, req_b)
    assert res_b.promotion_status == PromotionStatus.PROMOTED

    # Verify Policy A is now RETIRED and Policy B is ACTIVE
    active_now = await PolicyLifecycleService.get_active_policy(db_session, m1.id)
    assert active_now.policy_id == "cand_promo_2"

    # 3. Rollback to Policy A
    roll_req = PolicyRollbackRequest(
        merchant_id=m1.id,
        target_policy_id="cand_promo_1",
        target_policy_version="merchant-policy/v1",
        reason="Emergency rollback to Policy A"
    )
    roll_res = await PolicyLifecycleService.rollback_policy(db_session, roll_req)
    assert roll_res.status == "ROLLED_BACK"
    assert roll_res.target_policy_id == "cand_promo_1"
    assert roll_res.previous_active_policy_id == "cand_promo_2"

    # Verify Policy A is ACTIVE again
    active_after = await PolicyLifecycleService.get_active_policy(db_session, m1.id)
    assert active_after.policy_id == "cand_promo_1"


@pytest.mark.asyncio
async def test_policy_rollback_rejected_when_historical_policy_fails_fresh_safety(db_session, seed_lifecycle_db):
    """Rollback is REJECTED if historical policy fails current Phase 8.6 safety rules."""
    m1, p1 = seed_lifecycle_db

    # 1. Promote Policy A
    cand_a = PolicyCandidate(
        candidate_id="cand_promo_1",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p1.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Policy A"
    )
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m1.id, candidate_policy_id="cand_promo_1", candidate_policy=cand_a, reason="Promote A"))

    # 2. Promote Policy B
    for i in range(25):
        db_session.add(PolicyMemoryRecord(
            id=f"mem_c2_{i}", merchant_id=m1.id, opportunity_id=f"opp_c2b_{i}", buyer_context_key="ctx_lcyc",
            scenario_id="scen_lcyc", policy_id="cand_promo_2", policy_version="merchant-policy/v1", experiment_id="exp_lcyc_1",
            variant="TREATMENT", evidence_id=f"evi_c2b_{i}", evidence_source="SIMULATED", outcome_type="TEST_MODE_COMPLETED",
            learning_eligible=True, reward_id=f"rew_c2b_{i}", reward_version="merchant-reward/v1", formula_version="contribution-formula/v1",
            reward_state="FINAL", is_admissible=True, is_safety_violation=False, is_current=True, reward_contribution_paise=60000,
            observed_at=datetime.now(timezone.utc), idempotency_key=f"idemp_c2b_{i}"
        ))
    await db_session.commit()

    cand_b = PolicyCandidate(
        candidate_id="cand_promo_2",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],  # NO_OFFER product-free
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Policy B"
    )
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m1.id, candidate_policy_id="cand_promo_2", candidate_policy=cand_b, reason="Promote B"))

    # 3. Simulate inventory change: product p1 stock drops to 0!
    p1.inventory_quantity = 0
    await db_session.commit()

    # 4. Attempt rollback to Policy A (which requires product p1 in stock)
    roll_req = PolicyRollbackRequest(
        merchant_id=m1.id,
        target_policy_id="cand_promo_1",
        target_policy_version="merchant-policy/v1",
        reason="Attempt rollback to out-of-stock product"
    )
    roll_res = await PolicyLifecycleService.rollback_policy(db_session, roll_req)

    assert roll_res.status == "REJECTED"
    assert PromotionFailureCode.SAFETY_GATE_REJECTED in roll_res.failure_codes

    # Active policy must remain Policy B
    active_now = await PolicyLifecycleService.get_active_policy(db_session, m1.id)
    assert active_now.policy_id == "cand_promo_2"


@pytest.mark.asyncio
async def test_fastapi_lifecycle_endpoints(client: AsyncClient, seed_lifecycle_db):
    """FastAPI endpoints for promotion, rollback, active retrieval, and history work correctly."""
    m1, p1 = seed_lifecycle_db

    # 1. Promote
    resp_prom = await client.post(
        "/api/v1/policy-lifecycle/promote",
        json={
            "merchant_id": m1.id,
            "candidate_policy_id": "cand_promo_1",
            "candidate_policy_version": "merchant-policy/v1",
            "candidate_policy": {
                "candidate_id": "cand_promo_1",
                "strategy_type": "SINGLE_PRODUCT",
                "product_ids": [p1.id],
                "validation_status": "APPROVED",
                "rationale": "FastAPI promotion"
            },
            "reason": "FastAPI test"
        }
    )
    assert resp_prom.status_code == 200
    data_prom = resp_prom.json()
    assert data_prom["promotion_status"] == "PROMOTED"

    # 2. Get Active
    resp_act = await client.get(f"/api/v1/policy-lifecycle/active/{m1.id}")
    assert resp_act.status_code == 200
    data_act = resp_act.json()
    assert data_act["policy_id"] == "cand_promo_1"
    assert data_act["lifecycle_status"] == "ACTIVE"

    # 3. Get History
    resp_hist = await client.get(f"/api/v1/policy-lifecycle/history/{m1.id}")
    assert resp_hist.status_code == 200
    data_hist = resp_hist.json()
    assert len(data_hist) >= 1

    # 4. Get Versions
    resp_ver = await client.get(f"/api/v1/policy-lifecycle/versions/{m1.id}")
    assert resp_ver.status_code == 200
    data_ver = resp_ver.json()
    assert len(data_ver) >= 1
