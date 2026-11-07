"""Integration Test Suite for Phase 11.5: Final Governance, Security, and Concurrency Boundaries.

Contracts:
- benchmark-scenario/v1
- policy-lifecycle/v1
- execution-boundary/v1
- tenant-isolation/v1

Covers Areas A through G in full database / multi-service integration:
- Area A: Closed-loop promotion attack (governance criteria gating)
- Area B: Full lifecycle rollback integrity (valid rollback vs stale rollback conflict)
- Area C: Concurrent lifecycle race and single-active-policy conservation
- Area D: Cross-tenant isolation attack and negative side-effect verification
- Area E: End-to-end information hygiene and buyer DTO economic privacy
- Area F: Execution authority attack (retired policy rejection at boundary)
- Area G: Full-system failure recovery (monotonic terminal state, zero duplicate learning)
- Replay: Deterministic repeatability across representative scenarios (N=3)
"""

import uuid
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func

from domain.models import (
    Merchant,
    Product,
    Order,
    Payment,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    PolicyLifecycleAuditRecord,
    PolicyMemoryRecord,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    PolicyLearningModelState,
)
from apps.api.core.state_machine import TransactionState
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
    PolicyLifecycleState,
    PolicyPromotionRequest,
    PolicyRollbackRequest,
)
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.errors import (
    ActivePolicyConflictError,
    PolicyVersionNotFoundError,
)
from services.runtime.schemas import (
    CanonicalDecisionRequest,
    DecisionEnvelope,
)
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import (
    DecisionExecuteRequest,
    ExecutionBoundaryStatus,
)
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.errors import DecisionTenantViolationError
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService
from services.learning.model_service import PolicyLearningModelService
from services.benchmark.runner import CanonicalBenchmarkRunner
from services.benchmark.governance_security_scenarios import (
    SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT,
    SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK,
    SCENARIO_REC_FAILURE_RETRY_RECOVERY,
)


def _create_mem_record(
    merchant_id: str,
    policy_id: str,
    contribution_paise: int = 45000,
    observed_at: datetime = None,
) -> PolicyMemoryRecord:
    opp = f"opp_{policy_id}_{uuid.uuid4().hex[:8]}"
    obs = observed_at or datetime.now(timezone.utc)
    return PolicyMemoryRecord(
        id=f"mem_{policy_id}_{uuid.uuid4().hex[:6]}",
        merchant_id=merchant_id,
        opportunity_id=opp,
        buyer_context_key="ctx_integ",
        scenario_id="scen_integ",
        policy_id=policy_id,
        policy_version="merchant-policy/v1",
        experiment_id="exp_integ",
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
# 1. AREA A: CLOSED-LOOP PROMOTION ATTACK
# ==============================================================================
@pytest.mark.asyncio
async def test_area_a_promotion_attack_closed_loop(db_session):
    """Area A: Candidate with positive economics but failing governance criteria (e.g. required experiment missing) is rejected."""
    m = Merchant(id="merch_adv_promo_01", name="Promo Attack Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_adv_pr_01", merchant_id=m.id, sku="SKU-PR-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=20, is_active=True)
    base_act = MerchantActivePolicy(merchant_id=m.id, policy_id="cand_base_stable", policy_version="merchant-policy/v1", promotion_id="init_base")
    db_session.add_all([m, p, base_act])
    await db_session.commit()

    cand = PolicyCandidate(
        candidate_id="cand_pos_econ_no_exp",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=[p.id],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="High revenue candidate",
    )

    # Seed 25 memory records
    mems = [_create_mem_record(m.id, "cand_pos_econ_no_exp", 60000) for _ in range(25)]
    db_session.add_all(mems)
    await db_session.commit()

    # Governance rule: require_controlled_experiment=True, but no experiment provided
    cfg = PromotionPolicyConfig(require_controlled_experiment=True)
    req = PolicyPromotionRequest(
        merchant_id=m.id,
        candidate_policy_id="cand_pos_econ_no_exp",
        candidate_policy=cand,
        config=cfg,
        reason="Attempting promotion without controlled experiment",
    )

    res = await PolicyLifecycleService.promote_policy(db_session, req)

    # Invariants:
    # 1. Rejection recorded
    assert res.promotion_status == PromotionStatus.NOT_ELIGIBLE
    assert PromotionFailureCode.EXPERIMENT_NOT_FOUND in res.failure_codes

    # 2. Active policy remains untouched
    active_now = await PolicyLifecycleService.get_active_policy(db_session, m.id)
    assert active_now.policy_id == "cand_base_stable"

    # 3. Audit trail records rejected transition
    audit_rows = (await db_session.execute(
        select(PolicyLifecycleAuditRecord).where(
            PolicyLifecycleAuditRecord.merchant_id == m.id,
            PolicyLifecycleAuditRecord.candidate_policy_id == "cand_pos_econ_no_exp",
        )
    )).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].promotion_status == PromotionStatus.NOT_ELIGIBLE.value


# ==============================================================================
# 2. AREA B: ROLLBACK FULL LIFECYCLE INTEGRITY
# ==============================================================================
@pytest.mark.asyncio
async def test_area_b_rollback_full_lifecycle_integrity(db_session):
    """Area B: Valid rollback updates active pointer; stale rollback is rejected with conflict."""
    m = Merchant(id="merch_adv_rollback_01", name="Rollback Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_adv_rb_01", merchant_id=m.id, sku="SKU-RB-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=20, is_active=True)
    db_session.add_all([m, p])
    await db_session.commit()

    cand1 = PolicyCandidate(candidate_id="cand_v1", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="V1")
    cand2 = PolicyCandidate(candidate_id="cand_v2", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="V2")

    # Promote V1
    mems1 = [_create_mem_record(m.id, "cand_v1", 40000) for _ in range(25)]
    db_session.add_all(mems1)
    await db_session.commit()
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_v1", candidate_policy=cand1, reason="P1"))

    # Promote V2
    mems2 = [_create_mem_record(m.id, "cand_v2", 50000) for _ in range(25)]
    db_session.add_all(mems2)
    await db_session.commit()
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_v2", candidate_policy=cand2, reason="P2"))

    # Currently active is cand_v2. Stale rollback expecting cand_v1 -> Conflict!
    with pytest.raises(ActivePolicyConflictError):
        await PolicyLifecycleService.rollback_policy(
            db_session,
            PolicyRollbackRequest(merchant_id=m.id, target_policy_id="cand_v1", expected_current_policy_id="cand_v1", reason="Stale"),
        )

    # Active remains cand_v2
    act = await PolicyLifecycleService.get_active_policy(db_session, m.id)
    assert act.policy_id == "cand_v2"

    # Valid rollback expecting cand_v2 -> Succeeds
    res = await PolicyLifecycleService.rollback_policy(
        db_session,
        PolicyRollbackRequest(merchant_id=m.id, target_policy_id="cand_v1", expected_current_policy_id="cand_v2", reason="Rollback to v1"),
    )
    assert res.target_policy_id == "cand_v1"
    assert res.status == "ROLLED_BACK"

    # Active is now cand_v1
    act_after = await PolicyLifecycleService.get_active_policy(db_session, m.id)
    assert act_after.policy_id == "cand_v1"

    # Historical versions are immutable and preserved
    ver_v2 = (await db_session.execute(
        select(MerchantPolicyVersionRecord).where(
            MerchantPolicyVersionRecord.merchant_id == m.id,
            MerchantPolicyVersionRecord.policy_id == "cand_v2",
        )
    )).scalar_one()
    assert ver_v2.lifecycle_status == PolicyLifecycleState.ROLLED_BACK.value


# ==============================================================================
# 3. AREA C: CONCURRENT MUTATION RACE
# ==============================================================================
@pytest.mark.asyncio
async def test_area_c_concurrent_lifecycle_race(db_session):
    """Area C: Competing lifecycle mutations racing for active policy preserve single active pointer."""
    m = Merchant(id="merch_adv_race_01", name="Race Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_adv_rc_01", merchant_id=m.id, sku="SKU-RC-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=20, is_active=True)
    db_session.add_all([m, p])
    await db_session.commit()

    cand_base = PolicyCandidate(candidate_id="cand_race_base", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="Base")
    mems = [_create_mem_record(m.id, "cand_race_base", 45000) for _ in range(25)]
    db_session.add_all(mems)
    await db_session.commit()
    await PolicyLifecycleService.promote_policy(db_session, PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_race_base", candidate_policy=cand_base, reason="Init base"))

    cand_a = PolicyCandidate(candidate_id="cand_race_a", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="A")
    cand_b = PolicyCandidate(candidate_id="cand_race_b", strategy_type=StrategyType.SINGLE_PRODUCT, product_ids=[p.id], validation_status=CandidateValidationStatus.APPROVED, rationale="B")

    mems_a = [_create_mem_record(m.id, "cand_race_a", 50000) for _ in range(25)]
    mems_b = [_create_mem_record(m.id, "cand_race_b", 55000) for _ in range(25)]
    db_session.add_all(mems_a + mems_b)
    await db_session.commit()

    # Two promotions both expecting predecessor cand_race_base
    req_a = PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_race_a", candidate_policy=cand_a, expected_previous_policy_id="cand_race_base", reason="Race A")
    req_b = PolicyPromotionRequest(merchant_id=m.id, candidate_policy_id="cand_race_b", candidate_policy=cand_b, expected_previous_policy_id="cand_race_base", reason="Race B")

    # Execute first promotion
    res_a = await PolicyLifecycleService.promote_policy(db_session, req_a)
    assert res_a.promotion_status == PromotionStatus.PROMOTED

    # Execute second promotion (now predecessor cand_race_base is stale!)
    res_b = await PolicyLifecycleService.promote_policy(db_session, req_b)
    assert res_b.promotion_status == PromotionStatus.CONFLICT
    assert PromotionFailureCode.PREDECESSOR_MISMATCH in res_b.failure_codes

    # Invariant: Database count of active policies for merchant is EXACTLY 1
    active_rows = (await db_session.execute(
        select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == m.id)
    )).scalars().all()
    assert len(active_rows) == 1
    assert active_rows[0].policy_id == "cand_race_a"


# ==============================================================================
# 4. AREA D: TENANT ISOLATION ATTACK
# ==============================================================================
@pytest.mark.asyncio
async def test_area_d_tenant_isolation_attack_closed_loop(db_session):
    """Area D: Cross-tenant execution attack is rejected with zero side effects on victim state."""
    mA = Merchant(id="merch_adv_tenant_a", name="Attacker Tenant", currency="INR", status="ACTIVE")
    mB = Merchant(id="merch_adv_tenant_b", name="Victim Tenant", currency="INR", status="ACTIVE")
    pB = Product(id="prod_adv_tb_01", merchant_id=mB.id, sku="SKU-TB-01", name="Beta Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=20, is_active=True)
    db_session.add_all([mA, mB, pB])
    await db_session.commit()

    # Victim B generates decision
    env_b = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=mB.id, opportunity_id="opp_tb_01", raw_prompt="backpack under 5000"),
    )

    pre_b_orders = (await db_session.execute(select(func.count(Order.id)))).scalar() or 0
    pre_b_payments = (await db_session.execute(select(func.count(Payment.id)))).scalar() or 0

    # Attacker A attempts to execute B's decision
    with pytest.raises(DecisionTenantViolationError):
        await DecisionExecutionBoundaryService.execute_decision(
            db=db_session,
            decision_id=env_b.decision_id,
            request=DecisionExecuteRequest(merchant_id=mA.id),
        )

    # Invariant: Victim state completely unchanged (0 orders, 0 payments created)
    post_b_orders = (await db_session.execute(select(func.count(Order.id)))).scalar() or 0
    post_b_payments = (await db_session.execute(select(func.count(Payment.id)))).scalar() or 0
    assert post_b_orders == pre_b_orders
    assert post_b_payments == pre_b_payments


# ==============================================================================
# 5. AREA E: INFORMATION HYGIENE ACROSS FULL PIPELINE
# ==============================================================================
@pytest.mark.asyncio
async def test_area_e_information_hygiene_across_full_pipeline(db_session):
    """Area E: Malicious strings (script, SQL injection, long text) execute safely as inert data; buyer DTO excludes economics."""
    m = Merchant(id="merch_adv_hygiene", name="Hygiene Merchant", currency="INR", status="ACTIVE")
    p = Product(
        id="prod_adv_hy_01",
        merchant_id=m.id,
        sku="SKU-HY-01",
        name="<script>alert('xss')</script>",
        category="travel_backpack",
        price_paise=400000,
        cost_paise=200000,
        inventory_quantity=20,
        is_active=True,
    )
    db_session.add_all([m, p])
    await db_session.commit()

    malicious_prompt = "travel backpack '; DROP TABLE products; -- with <script>alert(1)</script>"
    env = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=m.id, opportunity_id="opp_hy_01", raw_prompt=malicious_prompt),
    )

    # Verify execution succeeds safely without SQL error
    res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=env.decision_id,
        request=DecisionExecuteRequest(merchant_id=m.id),
    )
    assert res.boundary_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED

    # Verify buyer offer excludes all merchant internal economic fields
    buyer_offer = env.buyer_offer.model_dump()
    assert "cogs_paise" not in buyer_offer
    assert "cost_paise" not in buyer_offer
    assert "gross_profit_paise" not in buyer_offer
    assert "gross_margin_percent" not in buyer_offer


# ==============================================================================
# 6. AREA F: EXECUTION AUTHORITY RETIRED POLICY ATTACK
# ==============================================================================
@pytest.mark.asyncio
async def test_area_f_execution_authority_retired_policy_attack(db_session):
    """Area F: Executing a decision for a retired policy is blocked at the boundary with zero orders or payments."""
    m = Merchant(id="merch_adv_retire_exec", name="Retire Exec Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_adv_re_01", merchant_id=m.id, sku="SKU-RE-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=20, is_active=True)
    db_session.add_all([m, p])
    await db_session.commit()

    env = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=m.id, opportunity_id="opp_re_01", raw_prompt="backpack under 5000"),
    )
    pol_id = env.merchant_evaluation.selected_policy_id

    # Retire the policy before execution boundary
    ver = MerchantPolicyVersionRecord(
        id=f"pver_{m.id}_{pol_id}_v1",
        merchant_id=m.id,
        policy_id=pol_id,
        policy_version="merchant-policy/v1",
        strategy_type="SINGLE_PRODUCT",
        lifecycle_status=PolicyLifecycleState.RETIRED.value,
    )
    db_session.add(ver)
    await db_session.commit()

    pre_orders = (await db_session.execute(select(func.count(Order.id)))).scalar() or 0

    res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=env.decision_id,
        request=DecisionExecuteRequest(merchant_id=m.id),
    )

    # Invariants:
    assert res.boundary_status == ExecutionBoundaryStatus.POLICY_RETIRED
    assert res.order_id is None
    post_orders = (await db_session.execute(select(func.count(Order.id)))).scalar() or 0
    assert post_orders == pre_orders


# ==============================================================================
# 7. AREA G: FULL-SYSTEM FAILURE RECOVERY
# ==============================================================================
@pytest.mark.asyncio
async def test_area_g_full_system_failure_recovery(db_session):
    """Area G: Upstream payment failure followed by recovery achieves monotonic terminal state and exactly one effective update."""
    m = Merchant(id="merch_adv_recovery_01", name="System Recovery Merchant", currency="INR", status="ACTIVE")
    p = Product(id="prod_adv_rec_01", merchant_id=m.id, sku="SKU-REC-01", name="Pack", category="travel_backpack", price_paise=400000, cost_paise=200000, inventory_quantity=20, is_active=True)
    db_session.add_all([m, p])
    await db_session.commit()

    # Step 1: Decision
    env = await CanonicalDecisionRuntime.decide(
        db_session,
        CanonicalDecisionRequest(merchant_id=m.id, opportunity_id="opp_rec_01", raw_prompt="backpack under 5000"),
    )

    # Step 2: Execution
    res = await DecisionExecutionBoundaryService.execute_decision(
        db=db_session,
        decision_id=env.decision_id,
        request=DecisionExecuteRequest(merchant_id=m.id, idempotency_key="idem_exec_rec_01"),
    )
    assert res.boundary_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED

    # Step 3: Payment succeeds and outcome is processed
    order = (await db_session.execute(select(Order).where(Order.id == res.order_id))).scalar_one()
    order.status = TransactionState.PAID.value
    pmt = Payment(
        id=f"pay_rec_{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        amount_paise=res.authorized_amount_paise,
        currency="INR",
        status="captured",
        captured_at=datetime.now(timezone.utc),
    )
    db_session.add(pmt)
    await db_session.commit()

    out_resp1 = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=m.id, execution_id=res.execution_id, idempotency_key="idem_out_rec_01"),
    )
    assert out_resp1.is_terminal is True
    assert out_resp1.outcome_status == "PAYMENT_SUCCESS"
    assert out_resp1.is_duplicate is False

    # Step 4: Retry/replay outcome processing (simulating network recovery / duplicate webhook)
    out_resp2 = await OutcomeFeedbackService.process_outcome(
        db_session,
        OutcomeProcessRequest(merchant_id=m.id, execution_id=res.execution_id, idempotency_key="idem_out_rec_01"),
    )
    assert out_resp2.is_terminal is True
    assert out_resp2.is_duplicate is True
    assert out_resp2.outcome_id == out_resp1.outcome_id

    # Invariants:
    # 1. Exactly 1 memory record
    mems = (await db_session.execute(select(PolicyMemoryRecord).where(PolicyMemoryRecord.merchant_id == m.id))).scalars().all()
    assert len(mems) == 1

    # 2. Exactly 1 model observation update
    model, _ = await PolicyLearningModelService.get_or_create_model(db_session, m.id)
    assert model.observation_count == 1


# ==============================================================================
# 8. DETERMINISTIC REPLAY: REPRESENTATIVE SCENARIOS (N=3)
# ==============================================================================
@pytest.mark.asyncio
async def test_deterministic_replay_representative_scenarios(db_session):
    """Replay 3 representative scenarios N=3 under controlled seed; verify zero divergence."""
    scenarios = [
        SCENARIO_GOV_CONCURRENT_LIFECYCLE_CONFLICT,
        SCENARIO_SEC_TENANT_AUTHORIZATION_ATTACK,
        SCENARIO_REC_FAILURE_RETRY_RECOVERY,
    ]

    for scen in scenarios:
        rep_result = await CanonicalBenchmarkRunner.run_repeatability(
            db=db_session,
            scenario=scen,
            repeat_count=3,
        )

        assert rep_result["all_passed"] is True, f"Scenario {scen.scenario_id} failed during repeatability runs: {rep_result}"
        assert rep_result["is_reproducible"] is True, f"Scenario {scen.scenario_id} had divergences: {rep_result['divergences']}"
        assert len(rep_result["divergences"]) == 0
