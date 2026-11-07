"""Unit Test Suite for Phase 11.5: Governance, Security, and Concurrency Boundaries.

Contracts:
- policy-lifecycle/v1
- execution-boundary/v1
- outcome-feedback/v1
- canonical-decision/v1

Covers Areas A through F at unit and boundary level:
- Area A: Promotion / Lifecycle invariants (insufficient evidence, positive economics != promotion, idempotency, single active pointer)
- Area B: Rollback integrity (valid rollback succeeds, stale rollback raises ActivePolicyConflictError)
- Area C: Concurrent mutation & optimistic concurrency protection
- Area D: Authoritative backend tenant authorization rejection
- Area E: Information hygiene (safe malicious strings as inert text, buyer DTO economic privacy)
- Area F: Execution authority rejection of invalid / retired governance state
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from domain.models import (
    Merchant,
    Product,
    PolicyMemoryRecord,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
)
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    IncentiveProposal,
)
from services.lifecycle.schemas import (
    PromotionPolicyConfig,
    PromotionFailureCode,
    PromotionStatus,
    PolicyPromotionRequest,
    PolicyRollbackRequest,
)
from services.lifecycle.evaluator import PolicyPromotionEvaluator
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.errors import (
    ActivePolicyConflictError,
    PolicyVersionNotFoundError,
)
from services.boundary.schemas import (
    DecisionExecuteRequest,
    ExecutionBoundaryStatus,
)
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.errors import DecisionTenantViolationError
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService
from services.outcome.errors import OutcomeTenantViolationError
from services.runtime.schemas import (
    CanonicalDecisionRequest,
    BuyerOfferView,
)
from services.runtime.service import CanonicalDecisionRuntime


def _create_memory_record(
    policy_id: str,
    contribution_paise: int,
    observed_at: datetime = None,
    buyer_context_key: str = "ctx_unit",
    opportunity_id: str = None,
    merchant_id: str = "merch_unit_gov",
) -> PolicyMemoryRecord:
    opp = opportunity_id or f"opp_{policy_id}_{uuid.uuid4().hex[:8]}"
    obs = observed_at or datetime.now(timezone.utc)
    return PolicyMemoryRecord(
        id=f"mem_{policy_id}_{uuid.uuid4().hex[:6]}",
        merchant_id=merchant_id,
        opportunity_id=opp,
        buyer_context_key=buyer_context_key,
        scenario_id="scen_unit",
        policy_id=policy_id,
        policy_version="merchant-policy/v1",
        experiment_id="exp_unit",
        experiment_version="policy-experiment/v1",
        variant="TREATMENT",
        evidence_id=f"evi_{uuid.uuid4().hex[:6]}",
        evidence_source="SIMULATED",
        outcome_type="TEST_MODE_COMPLETED",
        learning_eligible=True,
        reward_id=f"rew_{uuid.uuid4().hex[:6]}",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state="FINAL",
        is_admissible=True,
        is_safety_violation=False,
        is_current=True,
        reward_contribution_paise=contribution_paise,
        idempotency_key=f"idem_{opp}",
        observed_at=obs,
    )


# ==============================================================================
# AREA A: PROMOTION / LIFECYCLE ATTACK
# ==============================================================================

def test_area_a_candidate_insufficient_evidence_never_promotes():
    """Area A.1: Candidate with insufficient observations (5 < 20) is strictly rejected."""
    cand_id = "cand_low_obs"
    cfg = PromotionPolicyConfig(min_learning_opportunities=20)

    # Only 5 memory records
    records = [_create_memory_record(cand_id, 40000) for _ in range(5)]

    is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id=cand_id,
        config=cfg,
        memory_records=records,
        baseline_records=[],
        candidate_policy_version="merchant-policy/v1",
    )

    assert is_eligible is False
    assert PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes


def test_area_a_candidate_positive_economics_governance_ineligible_rejected():
    """Area A.2: High positive contribution (+50,000 paise) CANNOT bypass baseline underperformance.

    Invariant: POSITIVE RESULT != AUTOMATIC PROMOTION.
    """
    cand_id = "cand_pos_econ_underperform"
    cfg = PromotionPolicyConfig(min_learning_opportunities=20)

    # Candidate has positive 50,000 paise contribution
    cand_records = [_create_memory_record(cand_id, 50000) for _ in range(25)]
    # Baseline has 70,000 paise contribution (candidate underperforms baseline)
    base_records = [_create_memory_record("cand_baseline", 70000) for _ in range(25)]

    is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id=cand_id,
        config=cfg,
        memory_records=cand_records,
        baseline_records=base_records,
        candidate_policy_version="merchant-policy/v1",
    )

    assert is_eligible is False
    assert PromotionFailureCode.NO_IMPROVEMENT_OVER_BASELINE in failure_codes


@pytest.mark.asyncio
async def test_area_a_promotion_idempotency_and_single_active_invariant(db_session):
    """Area A.3 & A.4: Repeated promotion of active policy is idempotent; exactly 1 active policy exists."""
    m = Merchant(id="merch_unit_promo_idemp", name="Unit Promo Merchant", currency="INR", status="ACTIVE")
    p = Product(
        id="prod_unit_promo_01",
        merchant_id=m.id,
        sku="SKU-PRM-01",
        name="Pack",
        category="travel_backpack",
        price_paise=400000,
        cost_paise=200000,
        inventory_quantity=10,
        is_active=True,
    )
    db_session.add_all([m, p])
    await db_session.commit()

    cand = PolicyCandidate(
        candidate_id="cand_unit_promo_valid",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Unit test valid candidate",
    )

    # Seed 25 memory records for eligibility
    mems = [_create_memory_record("cand_unit_promo_valid", 45000, merchant_id=m.id) for _ in range(25)]
    db_session.add_all(mems)
    await db_session.commit()

    req = PolicyPromotionRequest(
        merchant_id=m.id,
        candidate_policy_id="cand_unit_promo_valid",
        candidate_policy=cand,
        reason="Initial promotion",
    )

    # Attempt 1: Promotes
    res1 = await PolicyLifecycleService.promote_policy(db_session, req)
    assert res1.promotion_status == PromotionStatus.PROMOTED

    # Attempt 2: Idempotent replay
    res2 = await PolicyLifecycleService.promote_policy(db_session, req)
    assert res2.promotion_status == PromotionStatus.PROMOTED
    assert res2.resulting_active_policy_id == "cand_unit_promo_valid"

    # Invariant: Exactly one active policy record in DB
    active_rows = (await db_session.execute(
        select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == m.id)
    )).scalars().all()
    assert len(active_rows) == 1
    assert active_rows[0].policy_id == "cand_unit_promo_valid"


# ==============================================================================
# AREA B: ROLLBACK INTEGRITY
# ==============================================================================

@pytest.mark.asyncio
async def test_area_b_valid_rollback_and_stale_rollback_rejection(db_session):
    """Area B: Valid rollback updates active pointer; stale rollback raises ActivePolicyConflictError."""
    m = Merchant(id="merch_unit_rollback", name="Rollback Unit Merchant", currency="INR", status="ACTIVE")
    p = Product(
        id="prod_unit_rb_01",
        merchant_id=m.id,
        sku="SKU-RB-01",
        name="Pack",
        category="travel_backpack",
        price_paise=400000,
        cost_paise=200000,
        inventory_quantity=10,
        is_active=True,
    )
    db_session.add_all([m, p])
    await db_session.commit()

    cand1 = PolicyCandidate(candidate_id="cand_rb_v1", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="V1")
    cand2 = PolicyCandidate(candidate_id="cand_rb_v2", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="V2")

    # Seed records and promote v1
    mems_v1 = [_create_memory_record("cand_rb_v1", 45000, merchant_id=m.id) for _ in range(25)]
    db_session.add_all(mems_v1)
    await db_session.commit()
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_rb_v1", candidate_policy=cand1, reason="Promote V1"))

    # Seed records and promote v2
    mems_v2 = [_create_memory_record("cand_rb_v2", 50000, merchant_id=m.id) for _ in range(25)]
    db_session.add_all(mems_v2)
    await db_session.commit()
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_rb_v2", candidate_policy=cand2, reason="Promote V2"))

    # Currently active is cand_rb_v2. Attempt stale rollback expecting current to be cand_rb_v1 -> Conflict!
    stale_rb = PolicyRollbackRequest(
        merchant_id=m.id,
        target_policy_id="cand_rb_v1",
        expected_current_policy_id="cand_rb_v1",  # WRONG expected current! Actual is v2!
        reason="Stale rollback attempt",
    )
    with pytest.raises(ActivePolicyConflictError):
        await PolicyLifecycleService.rollback_policy(db_session, stale_rb)

    # Active policy remains cand_rb_v2 intact
    active_now = await PolicyLifecycleService.get_active_policy(db_session, m.id)
    assert active_now.policy_id == "cand_rb_v2"

    # Now valid rollback expecting current to be cand_rb_v2 -> Succeeds!
    valid_rb = PolicyRollbackRequest(
        merchant_id=m.id,
        target_policy_id="cand_rb_v1",
        expected_current_policy_id="cand_rb_v2",
        reason="Valid rollback to v1",
    )
    res_rb = await PolicyLifecycleService.rollback_policy(db_session, valid_rb)
    assert res_rb.target_policy_id == "cand_rb_v1"
    assert res_rb.status == "ROLLED_BACK"

    active_after = await PolicyLifecycleService.get_active_policy(db_session, m.id)
    assert active_after.policy_id == "cand_rb_v1"


# ==============================================================================
# AREA C: CONCURRENT MUTATION / RACE PROTECTION
# ==============================================================================

@pytest.mark.asyncio
async def test_area_c_concurrent_mutation_optimistic_concurrency_protection(db_session):
    """Area C: Conflicting promotion with wrong expected predecessor returns CONFLICT."""
    m = Merchant(id="merch_unit_race", name="Race Concurrency Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_unit_race_01", merchant_id=m.id, sku="SKU-RC-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=10, is_active=True)
    db_session.add_all([m, p])
    await db_session.commit()

    cand_base = PolicyCandidate(candidate_id="cand_rc_base", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="Base")
    mems = [_create_memory_record("cand_rc_base", 45000, merchant_id=m.id) for _ in range(25)]
    db_session.add_all(mems)
    await db_session.commit()
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_rc_base", candidate_policy=cand_base, reason="Init base"))

    cand_target = PolicyCandidate(candidate_id="cand_rc_target", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="Target")

    # Mismatched expected previous policy
    req_conflict = PolicyPromotionRequest(
        merchant_id=m.id,
        candidate_policy_id="cand_rc_target",
        candidate_policy=cand_target,
        expected_previous_policy_id="cand_nonexistent_or_stale",
        reason="Conflicting race promotion",
    )
    res_conflict = await PolicyLifecycleService.promote_policy(db_session, req_conflict)

    assert res_conflict.promotion_status == PromotionStatus.CONFLICT
    assert PromotionFailureCode.PREDECESSOR_MISMATCH in res_conflict.failure_codes

    # Active policy remains cand_rc_base
    active_now = await PolicyLifecycleService.get_active_policy(db_session, m.id)
    assert active_now.policy_id == "cand_rc_base"


# ==============================================================================
# AREA D: AUTHORIZATION / TENANT ATTACK
# ==============================================================================

@pytest.mark.asyncio
async def test_area_d_backend_tenant_authorization_rejection(db_session):
    """Area D: Authoritative boundaries reject cross-tenant execution and outcome processing."""
    mA = Merchant(id="merch_unit_auth_a", name="Tenant A", currency="INR", status="ACTIVE")
    mB = Merchant(id="merch_unit_auth_b", name="Tenant B", currency="INR", status="ACTIVE")
    pB = Product(id="prod_auth_b_01", merchant_id=mB.id, sku="SKU-AB-01", name="B Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=10, is_active=True)
    db_session.add_all([mA, mB, pB])
    await db_session.commit()

    # B creates a decision
    env_b = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=mB.id, opportunity_id="opp_auth_b_01", raw_prompt="backpack under 5000"),
    )

    # 1. Tenant A attempts to execute Tenant B's decision -> Blocked by boundary
    with pytest.raises(DecisionTenantViolationError):
        await DecisionExecutionBoundaryService.execute_decision(
            db=db_session,
            decision_id=env_b.decision_id,
            request=DecisionExecuteRequest(merchant_id=mA.id),
        )

    # B executes cleanly
    exec_b = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=env_b.decision_id,
        request=DecisionExecuteRequest(merchant_id=mB.id),
    )

    # 2. Tenant A attempts to process Tenant B's outcome -> Blocked by outcome boundary
    with pytest.raises(OutcomeTenantViolationError):
        await OutcomeFeedbackService.process_outcome(
            db=db_session,
            request=OutcomeProcessRequest(merchant_id=mA.id, execution_id=exec_b.execution_id),
        )


# ==============================================================================
# AREA E: INFORMATION-HYGIENE / UNTRUSTED INPUT & PRIVACY DTO
# ==============================================================================

def test_area_e_information_hygiene_untrusted_input_and_privacy_dto():
    """Area E: Malicious strings are inert; buyer DTO strictly excludes private merchant economics."""
    # 1. Safe malicious inputs in DTO fields
    malicious_inputs = [
        "<script>alert('xss')</script>",
        "'; DROP TABLE merchants; --",
        "\nINJECTED_HEADER: admin\r\n",
        "A" * 4000,  # Long text
    ]

    for payload in malicious_inputs:
        # Buyer context handles untrusted string as pure text data
        req = CanonicalDecisionRequest(
            merchant_id="merch_test",
            opportunity_id="opp_xss",
            raw_prompt=f"backpack with {payload}",
        )
        assert payload in req.raw_prompt

    # 2. BuyerOfferView STRICT PRIVACY INVARIANT: No internal economics
    offer = BuyerOfferView(
        offer_id="off_test_01",
        strategy_type="BOUNDED_DISCOUNT",
        product_ids=["prod_01"],
        offered_price_paise=350000,
        currency="INR",
        display_discount_percent=12.5,
        rationale="12.5% discount applied",
    )
    serialized = offer.model_dump()

    # Verify absence of private merchant economic fields
    assert "cost_paise" not in serialized
    assert "cogs_paise" not in serialized
    assert "gross_profit_paise" not in serialized
    assert "gross_margin_percent" not in serialized
    assert "minimum_margin_percent" not in serialized
    assert "maximum_discount_percent" not in serialized


# ==============================================================================
# AREA F: EXECUTION AUTHORITY ATTACK
# ==============================================================================

@pytest.mark.asyncio
async def test_area_f_execution_boundary_rejects_invalid_governance_state(db_session):
    """Area F: Execution boundary rejects execution if policy has been retired or rolled back."""
    m = Merchant(id="merch_unit_gov_exec", name="Gov Exec Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_gov_exec_01", merchant_id=m.id, sku="SKU-GE-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=10, is_active=True)
    db_session.add_all([m, p])
    await db_session.commit()

    # Decision created for policy cand_retire_target
    env = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=m.id, opportunity_id="opp_ge_01", raw_prompt="backpack under 5000"),
    )
    selected_pol = env.merchant_evaluation.selected_policy_id

    # Simulate policy being retired before execution
    ver_rec = MerchantPolicyVersionRecord(
        id=f"pver_{m.id}_{selected_pol}_v1",
        merchant_id=m.id,
        policy_id=selected_pol,
        policy_version="merchant-policy/v1",
        strategy_type="SINGLE_PRODUCT",
        lifecycle_status="RETIRED",
    )
    db_session.add(ver_rec)
    await db_session.commit()

    # Execution boundary evaluates governance state
    res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=env.decision_id,
        request=DecisionExecuteRequest(merchant_id=m.id),
    )

    # Invariants: Execution rejected, no order created
    assert res.boundary_status == ExecutionBoundaryStatus.POLICY_RETIRED
    assert res.order_id is None
    assert "POLICY_RETIRED" in res.rejection_reasons[0]
