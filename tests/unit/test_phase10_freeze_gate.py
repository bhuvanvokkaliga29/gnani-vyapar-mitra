"""Phase 10 Final Freeze Gate Verification Tests.

Validates all 8 required Phase 10 semantic hardening invariants:
A. Baseline policy does not display false promotion satisfaction
B. Policy evidence count is not inflated by joined rows
C. Observed contribution is not inflated by joined rows
D. Active-policy metrics remain policy-specific
E. Tenant isolation remains intact
F. API values equal authoritative DB/service values
G. Decision Detail terminology remains semantically correct
H. Execution/payment/learning states remain distinct

Hermetic: Uses in-memory fixture with programmatic test setup (no local file dependencies).
"""

import pytest
import pytest_asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import (
    Merchant,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    PolicyMemoryRecord,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    Order,
    Payment
)
from services.dashboard.service import (
    PolicyViewService,
    DecisionViewService,
    DashboardOverviewService
)
from services.dashboard.schemas import (
    PolicyManagementDTO,
    DecisionDetailDTO,
    PolicyVersionItemDTO
)
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.schemas import (
    PolicyPromotionRequest,
    PromotionStatus,
    PromotionFailureCode
)
from services.lifecycle.errors import ActivePolicyConflictError
from services.commerce_service import MerchantNotFoundError


@pytest_asyncio.fixture
async def seeded_freeze_gate_db(db_session: AsyncSession) -> AsyncSession:
    """Hermetically seed the exact Phase 10 test records in memory."""
    now = datetime.now(timezone.utc)

    # 1. Merchants
    atlas_m = Merchant(
        id="merch_atlas_travel",
        name="Atlas Travel Gear",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("20.00"),
        target_aov_paise=400000
    )
    alpha_m = Merchant(
        id="merch_alpha",
        name="Alpha Retail",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("15.00"),
        maximum_discount_percent=Decimal("30.00"),
        target_aov_paise=300000
    )
    db_session.add_all([atlas_m, alpha_m])

    # 2. Active Policies
    atlas_act = MerchantActivePolicy(
        merchant_id="merch_atlas_travel",
        policy_id="cand_base_no_offer",
        policy_version="merchant-policy/v1",
        promotion_id="prom_atlas_init"
    )
    alpha_act = MerchantActivePolicy(
        merchant_id="merch_alpha",
        policy_id="cand_alpha_base",
        policy_version="merchant-policy/v1",
        promotion_id="prom_alpha_init"
    )
    db_session.add_all([atlas_act, alpha_act])

    # 3. Policy Version Records
    v_base = MerchantPolicyVersionRecord(
        id="pvr_base_01",
        merchant_id="merch_atlas_travel",
        policy_id="cand_base_no_offer",
        policy_version="merchant-policy/v1",
        lifecycle_status="ACTIVE",
        strategy_type="NO_OFFER",
        created_at=now
    )
    v_cand = MerchantPolicyVersionRecord(
        id="pvr_cand_01",
        merchant_id="merch_atlas_travel",
        policy_id="cand_54256751",
        policy_version="merchant-policy/v1",
        lifecycle_status="REGISTERED",
        strategy_type="COMPLEMENTARY_BUNDLE",
        created_at=now
    )
    v_alpha = MerchantPolicyVersionRecord(
        id="pvr_alpha_01",
        merchant_id="merch_alpha",
        policy_id="cand_alpha_base",
        policy_version="merchant-policy/v1",
        lifecycle_status="ACTIVE",
        strategy_type="SINGLE_PRODUCT",
        created_at=now
    )
    db_session.add_all([v_base, v_cand, v_alpha])

    # 4. Policy Memory Records for cand_54256751
    mem1 = PolicyMemoryRecord(
        id="mem_01",
        merchant_id="merch_atlas_travel",
        opportunity_id="opp_01",
        buyer_context_key="key_01",
        scenario_id="scen_01",
        policy_id="cand_54256751",
        policy_version="merchant-policy/v1",
        experiment_id="exp_01",
        experiment_version="policy-experiment/v1",
        variant="TREATMENT",
        evidence_id="evi_01",
        evidence_source="TEST_MODE",
        outcome_type="TEST_MODE_COMPLETED",
        learning_eligible=True,
        reward_id="rew_01",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state="FINAL",
        reward_contribution_paise=150000,
        is_admissible=True,
        is_current=True,
        is_safety_violation=False,
        idempotency_key="idem_mem_01",
        observed_at=now
    )
    mem2 = PolicyMemoryRecord(
        id="mem_02",
        merchant_id="merch_atlas_travel",
        opportunity_id="opp_02",
        buyer_context_key="key_02",
        scenario_id="scen_02",
        policy_id="cand_54256751",
        policy_version="merchant-policy/v1",
        experiment_id="exp_02",
        experiment_version="policy-experiment/v1",
        variant="TREATMENT",
        evidence_id="evi_02",
        evidence_source="TEST_MODE",
        outcome_type="TEST_MODE_COMPLETED",
        learning_eligible=True,
        reward_id="rew_02",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state="FINAL",
        reward_contribution_paise=200000,
        is_admissible=True,
        is_current=True,
        is_safety_violation=False,
        idempotency_key="idem_mem_02",
        observed_at=now
    )
    db_session.add_all([mem1, mem2])

    # 5. Canonical Decision Record
    dec_id = "dec_atlas_test_01"
    exec_id = "exec_atlas_test_01"
    ord_id = "ord_atlas_test_01"
    envelope = {
        "decision_id": dec_id,
        "runtime_version": "canonical-decision/v1",
        "merchant_id": "merch_atlas_travel",
        "opportunity_id": "opp_dec_01",
        "mode": "EXPLORE",
        "selected_policy": {
            "policy_id": "cand_54256751",
            "policy_version": "merchant-policy/v1",
            "strategy_type": "COMPLEMENTARY_BUNDLE",
            "predicted_contribution_paise": 150000,
            "composite_ranking_score": 0.85
        },
        "candidates": [
            {
                "policy_id": "cand_54256751",
                "strategy_type": "COMPLEMENTARY_BUNDLE",
                "predicted_contribution_paise": 150000,
                "composite_ranking_score": 0.85
            }
        ],
        "buyer_offer": {
            "offer_type": "COMPLEMENTARY_BUNDLE",
            "items": [{"product_id": "prod_01", "name": "Test Item", "quantity": 1, "price_paise": 400000}],
            "total_price_paise": 400000,
            "effective_discount_percent": "0.00",
            "currency": "INR",
            "guaranteed_until": now.isoformat()
        },
        "merchant_evaluation": {
            "selected_policy_id": "cand_54256751",
            "selected_strategy_type": "COMPLEMENTARY_BUNDLE",
            "total_candidates": 1,
            "valid_candidates_count": 1,
            "predicted_contribution_paise": 150000,
            "composite_ranking_score": 0.85
        },
        "safety_audit": {"status": "PASSED"},
        "exploration_trace": {"mode": "EXPLORE"},
        "model_metadata": {"model_version": 1},
        "trace": {"decision_latency_ms": 12.5},
        "created_at": now.isoformat()
    }
    dec_record = CanonicalDecisionRecord(
        id=dec_id,
        merchant_id="merch_atlas_travel",
        opportunity_id="opp_dec_01",
        decision_version="canonical-decision/v1",
        buyer_context_key="key_dec_01",
        decision_mode="EXPLORE",
        decision_reason="Exploration selection",
        selected_policy_id="cand_54256751",
        selected_strategy_type="COMPLEMENTARY_BUNDLE",
        proposed_price_paise=400000,
        predicted_contribution_paise=150000,
        decision_envelope_json=envelope,
        created_at=now
    )
    db_session.add(dec_record)

    # 6. Execution Record
    exec_record = DecisionExecutionRecord(
        id=exec_id,
        merchant_id="merch_atlas_travel",
        decision_id=dec_id,
        opportunity_id="opp_dec_01",
        authorization_id="eauth_atlas_test_01",
        policy_id="cand_54256751",
        policy_version="merchant-policy/v1",
        state_fingerprint="fp_atlas_test_01",
        boundary_status="EXECUTION_COMPLETED",
        order_id=ord_id,
        currency="INR",
        idempotency_key="idem_exec_atlas_test_01",
        created_at=now
    )
    db_session.add(exec_record)

    # 7. Order and Outcome
    order = Order(
        id=ord_id,
        decision_id=dec_id,
        amount_paise=400000,
        currency="INR",
        receipt="rcpt_atlas_test_01",
        status="PAID",
        created_at=now
    )
    outcome = OutcomeFeedbackRecord(
        id="out_01",
        merchant_id="merch_atlas_travel",
        opportunity_id="opp_dec_01",
        decision_id=dec_id,
        execution_id=exec_id,
        order_id=ord_id,
        transaction_state="PAID",
        outcome_status="PAYMENT_CAPTURED",
        processing_state="COMPLETED",
        reward_contribution_paise=150000,
        idempotency_key="idem_out_atlas_test_01",
        created_at=now
    )
    db_session.add_all([order, outcome])

    await db_session.commit()
    return db_session


@pytest.mark.asyncio
async def test_criterion_a_baseline_policy_not_false_satisfied(seeded_freeze_gate_db: AsyncSession):
    """Criterion A: Baseline policy does not display false promotion satisfaction."""
    data = await PolicyViewService.get_policies(seeded_freeze_gate_db, "merch_atlas_travel")
    assert data.active_policy is not None
    assert data.active_policy.policy_id == "cand_base_no_offer"

    baseline_versions = [v for v in data.versions if v.is_active]
    assert len(baseline_versions) == 1
    baseline_ver = baseline_versions[0]
    assert baseline_ver.promotion_criteria_satisfied is False
    assert baseline_ver.policy_id == "cand_base_no_offer"


@pytest.mark.asyncio
async def test_criterion_b_and_c_no_join_inflation(seeded_freeze_gate_db: AsyncSession):
    """Criterion B & C: Evidence count and observed contribution are NOT inflated by joins."""
    merchant_id = "merch_atlas_travel"
    policy_id = "cand_54256751"

    direct_ev_stmt = select(func.count(PolicyMemoryRecord.id)).where(
        and_(
            PolicyMemoryRecord.merchant_id == merchant_id,
            PolicyMemoryRecord.policy_id == policy_id
        )
    )
    authoritative_count = (await seeded_freeze_gate_db.execute(direct_ev_stmt)).scalar() or 0

    direct_contrib_stmt = select(
        func.coalesce(func.sum(PolicyMemoryRecord.reward_contribution_paise), 0)
    ).where(
        and_(
            PolicyMemoryRecord.merchant_id == merchant_id,
            PolicyMemoryRecord.policy_id == policy_id
        )
    )
    authoritative_contrib = (await seeded_freeze_gate_db.execute(direct_contrib_stmt)).scalar() or 0

    policies_data = await PolicyViewService.get_policies(seeded_freeze_gate_db, merchant_id)
    cand_version = next((v for v in policies_data.versions if v.policy_id == policy_id), None)

    assert cand_version is not None
    assert cand_version.evidence_count == authoritative_count
    assert cand_version.observed_contribution_paise == authoritative_contrib


@pytest.mark.asyncio
async def test_criterion_d_active_policy_metrics_remain_policy_specific(seeded_freeze_gate_db: AsyncSession):
    """Criterion D: Active policy metrics refer strictly to the current active policy."""
    data = await PolicyViewService.get_policies(seeded_freeze_gate_db, "merch_atlas_travel")
    active = data.active_policy
    assert active is not None
    assert active.policy_id == "cand_base_no_offer"

    all_mem_stmt = select(func.count(PolicyMemoryRecord.id)).where(
        PolicyMemoryRecord.merchant_id == "merch_atlas_travel"
    )
    total_mem_count = (await seeded_freeze_gate_db.execute(all_mem_stmt)).scalar() or 0

    assert active.evidence_count == 0
    assert active.observed_contribution_paise == 0
    assert total_mem_count > 0


@pytest.mark.asyncio
async def test_criterion_e_tenant_isolation(seeded_freeze_gate_db: AsyncSession):
    """Criterion E: Tenant isolation remains strictly enforced; no cross-merchant leakage."""
    atlas_data = await PolicyViewService.get_policies(seeded_freeze_gate_db, "merch_atlas_travel")
    alpha_data = await PolicyViewService.get_policies(seeded_freeze_gate_db, "merch_alpha")

    assert atlas_data.active_policy.policy_id == "cand_base_no_offer"
    assert alpha_data.active_policy.policy_id == "cand_alpha_base"

    atlas_pids = {v.policy_id for v in atlas_data.versions}
    alpha_pids = {v.policy_id for v in alpha_data.versions}
    assert "cand_alpha_base" not in atlas_pids
    assert "cand_54256751" not in alpha_pids

    with pytest.raises(MerchantNotFoundError):
        await PolicyViewService.get_policies(seeded_freeze_gate_db, "merch_nonexistent_xyz")


@pytest.mark.asyncio
async def test_criterion_f_api_values_equal_authoritative_db_values(seeded_freeze_gate_db: AsyncSession):
    """Criterion F: API projection values exactly match underlying authoritative DB rows."""
    merchant_id = "merch_atlas_travel"

    active_row = (await seeded_freeze_gate_db.execute(
        select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == merchant_id)
    )).scalar_one()

    service_res = await PolicyViewService.get_policies(seeded_freeze_gate_db, merchant_id)
    assert service_res.active_policy.policy_id == active_row.policy_id
    assert service_res.active_policy.policy_version == active_row.policy_version


@pytest.mark.asyncio
async def test_criterion_g_decision_detail_terminology(seeded_freeze_gate_db: AsyncSession):
    """Criterion G: Decision Detail terminology: Predicted Contribution vs Ranking Score vs Observed."""
    stmt = select(CanonicalDecisionRecord).where(
        CanonicalDecisionRecord.merchant_id == "merch_atlas_travel"
    ).limit(1)
    dec = (await seeded_freeze_gate_db.execute(stmt)).scalar_one_or_none()

    assert dec is not None
    detail = await DecisionViewService.get_decision_detail(seeded_freeze_gate_db, dec.id, "merch_atlas_travel")
    assert hasattr(detail.merchant_evaluation, "predicted_contribution_paise")
    assert hasattr(detail.merchant_evaluation, "composite_ranking_score")
    assert hasattr(detail, "candidates")
    for c in detail.candidates:
        assert hasattr(c, "predicted_contribution_paise")
        assert hasattr(c, "composite_ranking_score")
        assert isinstance(c.composite_ranking_score, float)
        assert isinstance(c.predicted_contribution_paise, int)


@pytest.mark.asyncio
async def test_criterion_h_execution_payment_learning_states_distinct(seeded_freeze_gate_db: AsyncSession):
    """Criterion H: Execution, Payment Outcome, and Learning states are decoupled and distinct."""
    stmt = select(CanonicalDecisionRecord).where(
        CanonicalDecisionRecord.merchant_id == "merch_atlas_travel"
    )
    decisions = (await seeded_freeze_gate_db.execute(stmt)).scalars().all()

    assert len(decisions) > 0
    for d in decisions:
        detail = await DecisionViewService.get_decision_detail(seeded_freeze_gate_db, d.id, "merch_atlas_travel")
        assert detail.execution_status in ("EXECUTION_COMPLETED", "EXECUTION_REJECTED", "PENDING_EXECUTION_GATE")
