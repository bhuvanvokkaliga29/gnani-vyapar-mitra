"""Canonical Benchmark Scenario Runner for Phase 11.1.

Orchestrates the execution of declarative scenarios against the real authoritative system:
1. Prepares isolated state
2. Applies explicit scenario setup
3. Invokes authoritative services (CanonicalDecisionRuntime -> Boundary -> Outcome)
4. Captures sanitized observations
5. Evaluates independent assertions
6. Produces versioned BenchmarkResult
"""

import time
import random
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any, Optional
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import (
    Merchant,
    Product,
    Order,
    Payment,
    MerchantActivePolicy,
    PolicyMemoryRecord,
)
from apps.api.core.state_machine import TransactionState
from services.runtime.service import CanonicalDecisionRuntime
from services.runtime.schemas import (
    CanonicalDecisionRequest,
    DecisionEnvelope,
    CANONICAL_DECISION_SCHEMA_VERSION,
)
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.schemas import DecisionExecuteRequest
from services.outcome.service import OutcomeFeedbackService
from services.outcome.schemas import OutcomeProcessRequest
from services.benchmark.schemas import (
    BenchmarkScenario,
    BenchmarkResult,
    BenchmarkSummary,
    BenchmarkStatus,
    BenchmarkExecutionMode,
    FailureClass,
    AssertionDiagnostic,
    ExpectationType,
    BenchmarkExpectation,
)
from services.benchmark.observer import BenchmarkObserver
from services.benchmark.assertions import AssertionEvaluator

logger = structlog.get_logger()


class CanonicalBenchmarkRunner:
    """Orchestrator executing benchmark scenarios through authoritative production services."""

    @classmethod
    async def run_scenario(
        cls,
        db: AsyncSession,
        scenario: BenchmarkScenario,
        run_id: Optional[str] = None,
    ) -> BenchmarkResult:
        """Execute a single benchmark scenario and return its verified result."""
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        t_start = time.perf_counter()
        started_at = datetime.now(timezone.utc)

        # Set scenario seed for local determinism
        random.seed(scenario.seed)

        decision_id = None
        execution_id = None
        outcome_id = None
        is_dup_exec = False
        is_dup_outcome = False
        observed = None
        diagnostics: List[AssertionDiagnostic] = []
        status = BenchmarkStatus.PASS

        try:
            # 1. Apply Scenario Setup (Declarative DB initial state)
            await cls._apply_setup(db, scenario)

            # 2. Invoke Authoritative Pipeline
            (
                decision_id,
                execution_id,
                outcome_id,
                is_dup_exec,
                is_dup_outcome,
                promo_status,
                promo_code,
                cross_tenant_rejected,
                stale_state_rejected,
            ) = await cls._execute_pipeline(db, scenario)

            # 3. Capture Authoritative Observations
            observed = await BenchmarkObserver.capture(
                db=db,
                merchant_id=scenario.merchant_id,
                opportunity_id=scenario.scenario_id,
                decision_id=decision_id,
                execution_id=execution_id,
                outcome_id=outcome_id,
                is_duplicate_execution=is_dup_exec,
                is_duplicate_outcome=is_dup_outcome,
                promotion_status=promo_status,
                promotion_failure_code=promo_code,
                cross_tenant_rejected=cross_tenant_rejected,
                stale_state_rejected=stale_state_rejected,
            )

            # 4. Compile Expectations (Invariants + Terminal State)
            all_expectations = list(scenario.expected_invariants)
            if scenario.expected_terminal_state:
                term_exps = cls._compile_terminal_expectations(scenario.expected_terminal_state)
                all_expectations.extend(term_exps)

            # 5. Evaluate Assertions
            diagnostics = AssertionEvaluator.evaluate_all(all_expectations, observed)

            # 6. Determine Pass/Fail Status
            failures = [d for d in diagnostics if not d.passed]
            if failures:
                status = BenchmarkStatus.FAIL
            else:
                status = BenchmarkStatus.PASS

        except Exception as ex:
            logger.exception("benchmark_scenario_execution_error", scenario_id=scenario.scenario_id, error=str(ex))
            # Infrastructure or harness failure must NEVER be disguised as PASS
            status = BenchmarkStatus.INCONCLUSIVE
            diagnostics.append(
                AssertionDiagnostic(
                    expectation_id="infrastructure_check",
                    expectation_type=ExpectationType.INVARIANT,
                    passed=False,
                    failure_class=FailureClass.INFRASTRUCTURE_FAILURE,
                    target_domain="infrastructure",
                    field_path=None,
                    expected="Clean execution without unhandled exception",
                    observed=str(ex),
                    message=f"Harness / Infrastructure exception: {str(ex)}",
                )
            )

        duration_ms = (time.perf_counter() - t_start) * 1000.0
        finished_at = datetime.now(timezone.utc)

        passed_count = sum(1 for d in diagnostics if d.passed)
        failed_count = sum(1 for d in diagnostics if not d.passed)

        return BenchmarkResult(
            run_id=run_id,
            scenario_id=scenario.scenario_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            category=scenario.category,
            merchant_id=scenario.merchant_id,
            seed=scenario.seed,
            assertions_total=len(diagnostics),
            assertions_passed=passed_count,
            assertions_failed=failed_count,
            observed_state=observed,
            expected_state=scenario.expected_terminal_state.model_dump() if scenario.expected_terminal_state else {},
            diagnostics=diagnostics,
            duration_ms=duration_ms,
        )

    @classmethod
    async def run_suite(
        cls,
        db: AsyncSession,
        scenarios: List[BenchmarkScenario],
        run_id: Optional[str] = None,
    ) -> Tuple[BenchmarkSummary, List[BenchmarkResult]]:
        """Execute an ordered suite of benchmark scenarios and return aggregate summary."""
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc)
        results: List[BenchmarkResult] = []
        categories: Dict[str, int] = {}

        t_total_start = time.perf_counter()

        for scen in scenarios:
            res = await cls.run_scenario(db, scen, run_id=run_id)
            results.append(res)
            cat_name = scen.category.value
            categories[cat_name] = categories.get(cat_name, 0) + 1

        finished_at = datetime.now(timezone.utc)
        duration_ms = (time.perf_counter() - t_total_start) * 1000.0

        passed_scenarios = sum(1 for r in results if r.status == BenchmarkStatus.PASS)
        failed_scenarios = sum(1 for r in results if r.status == BenchmarkStatus.FAIL)
        inconclusive_scenarios = sum(1 for r in results if r.status == BenchmarkStatus.INCONCLUSIVE)

        total_assertions = sum(r.assertions_total for r in results)
        passed_assertions = sum(r.assertions_passed for r in results)
        failed_assertions = sum(r.assertions_failed for r in results)

        summary = BenchmarkSummary(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            total_scenarios=len(scenarios),
            passed=passed_scenarios,
            failed=failed_scenarios,
            inconclusive=inconclusive_scenarios,
            assertions_total=total_assertions,
            assertions_passed=passed_assertions,
            assertions_failed=failed_assertions,
            categories=categories,
            duration_ms=duration_ms,
            reproducibility_status="VERIFIED" if failed_scenarios == 0 and inconclusive_scenarios == 0 else "DEGRADED",
        )

        return summary, results

    @classmethod
    async def run_repeatability(
        cls,
        db: AsyncSession,
        scenario: BenchmarkScenario,
        repeat_count: int = 3,
    ) -> Dict[str, Any]:
        """Execute the same scenario N times under the same seed and assert business state consistency."""
        runs: List[BenchmarkResult] = []
        for i in range(repeat_count):
            res = await cls.run_scenario(db, scenario, run_id=f"rep_{i+1}_{scenario.scenario_id}")
            runs.append(res)

        # Compare terminal business fields across runs (excluding non-deterministic UUIDs and timestamps)
        divergences = []
        ref_obs = runs[0].observed_state
        for idx, r in enumerate(runs[1:], start=2):
            cur_obs = r.observed_state
            if ref_obs and cur_obs:
                if ref_obs.selected_strategy != cur_obs.selected_strategy:
                    divergences.append(f"Run {idx} strategy {cur_obs.selected_strategy} != Run 1 {ref_obs.selected_strategy}")
                if ref_obs.boundary_status != cur_obs.boundary_status:
                    divergences.append(f"Run {idx} boundary_status {cur_obs.boundary_status} != Run 1 {ref_obs.boundary_status}")
                if ref_obs.outcome_status != cur_obs.outcome_status:
                    divergences.append(f"Run {idx} outcome_status {cur_obs.outcome_status} != Run 1 {ref_obs.outcome_status}")
                if ref_obs.reward_contribution_paise != cur_obs.reward_contribution_paise:
                    divergences.append(f"Run {idx} reward {cur_obs.reward_contribution_paise} != Run 1 {ref_obs.reward_contribution_paise}")

        is_reproducible = len(divergences) == 0 and all(r.status == BenchmarkStatus.PASS for r in runs)
        return {
            "scenario_id": scenario.scenario_id,
            "repeat_count": repeat_count,
            "all_passed": all(r.status == BenchmarkStatus.PASS for r in runs),
            "is_reproducible": is_reproducible,
            "divergences": divergences,
            "runs": [r.model_dump() for r in runs],
        }

    # ==================== Internal Pipeline Orchestration ====================

    @classmethod
    async def _apply_setup(cls, db: AsyncSession, scenario: BenchmarkScenario) -> None:
        """Seed declarative initial state into database."""
        init = scenario.initial_state
        # 1. Merchant
        if init.merchant:
            m = init.merchant
            stmt = select(Merchant).where(Merchant.id == m.merchant_id)
            existing_m = (await db.execute(stmt)).scalar_one_or_none()
            if not existing_m:
                new_m = Merchant(
                    id=m.merchant_id,
                    name=m.name,
                    currency=m.currency,
                    status=m.status,
                    business_objective=m.business_objective,
                    minimum_margin_percent=Decimal(str(m.minimum_margin_percent)),
                    maximum_discount_percent=Decimal(str(m.maximum_discount_percent)),
                    target_aov_paise=m.target_aov_paise,
                )
                db.add(new_m)
                await db.commit()

        # 2. Products
        if init.products:
            for p in init.products:
                stmt_p = select(Product).where(Product.id == p.product_id)
                existing_p = (await db.execute(stmt_p)).scalar_one_or_none()
                if not existing_p:
                    new_p = Product(
                        id=p.product_id,
                        merchant_id=scenario.merchant_id,
                        name=p.name,
                        sku=p.sku,
                        category=p.category,
                        price_paise=p.price_paise,
                        cost_paise=p.cost_paise,
                        inventory_quantity=p.inventory_quantity,
                        attributes=p.attributes,
                        is_active=p.is_active,
                    )
                    db.add(new_p)
            await db.commit()

        # 3. Active Policy
        if init.active_policy_id:
            stmt_act = select(MerchantActivePolicy).where(MerchantActivePolicy.merchant_id == scenario.merchant_id)
            act = (await db.execute(stmt_act)).scalar_one_or_none()
            if not act:
                new_act = MerchantActivePolicy(
                    merchant_id=scenario.merchant_id,
                    policy_id=init.active_policy_id,
                    policy_version="merchant-policy/v1",
                    promotion_id=f"prom_init_{scenario.scenario_id[:16]}",
                )
                db.add(new_act)
                await db.commit()

    @classmethod
    async def _execute_pipeline(
        cls,
        db: AsyncSession,
        scenario: BenchmarkScenario,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], bool, bool, Optional[str], Optional[str], Optional[bool], Optional[bool]]:
        """Invoke real production services sequentially and return entity IDs and adversarial test signals."""
        promo_status = None
        promo_code = None
        cross_tenant_rejected = None
        stale_state_rejected = None

        # Optional pre-evaluation hooks for Phase 11.4 adaptive testing
        if scenario.input_overrides.get("seed_future_evidence"):
            from datetime import timedelta
            from domain.models import PolicyMemoryRecord
            target_pol = scenario.input_overrides.get("promotion_target_policy_id", "cand_adapt_future_treatment")
            fut_mem = PolicyMemoryRecord(
                id=f"mem_fut_{uuid.uuid4().hex[:12]}",
                merchant_id=scenario.merchant_id,
                opportunity_id=f"opp_fut_{uuid.uuid4().hex[:8]}",
                buyer_context_key="key_future",
                scenario_id="scen_future",
                policy_id=target_pol,
                policy_version="merchant-policy/v1",
                experiment_id="exp_future",
                experiment_version="policy-experiment/v1",
                variant="TREATMENT",
                evidence_id=f"evi_fut_{uuid.uuid4().hex[:8]}",
                evidence_source="SIMULATED",
                outcome_type="TEST_MODE_COMPLETED",
                learning_eligible=True,
                reward_id=f"rew_fut_{uuid.uuid4().hex[:8]}",
                reward_version="merchant-reward/v1",
                formula_version="contribution-formula/v1",
                reward_state="FINAL",
                is_admissible=True,
                is_safety_violation=False,
                is_current=True,
                reward_contribution_paise=50000,
                idempotency_key=f"idemp_fut_{uuid.uuid4().hex[:8]}",
                observed_at=datetime.now(timezone.utc) + timedelta(days=5),
            )
            db.add(fut_mem)
            await db.commit()

        if scenario.input_overrides.get("seed_exhausted_exploration"):
            from sqlalchemy import and_
            from domain.models import MerchantExplorationState
            from services.exploration.schemas import MerchantExplorationConfig
            cfg = MerchantExplorationConfig()
            win_id = f"win_{scenario.merchant_id}"
            stmt_exp = select(MerchantExplorationState).where(
                and_(
                    MerchantExplorationState.merchant_id == scenario.merchant_id,
                    MerchantExplorationState.window_id == win_id
                )
            )
            exp_rec = (await db.execute(stmt_exp)).scalar_one_or_none()
            if not exp_rec:
                exp_rec = MerchantExplorationState(
                    id=f"exp_state_{scenario.merchant_id}_{win_id}",
                    merchant_id=scenario.merchant_id,
                    window_id=win_id,
                    opportunities_used=cfg.max_exploration_opportunities,
                    exposure_paise_used=cfg.max_exposure_paise,
                    consecutive_explorations=0,
                    policy_counts_json={},
                    context_counts_json={},
                    version=1,
                )
                db.add(exp_rec)
            else:
                exp_rec.opportunities_used = cfg.max_exploration_opportunities
                exp_rec.exposure_paise_used = cfg.max_exposure_paise
            await db.commit()

        # Check if scenario requests lifecycle promotion evaluation (e.g. lucky purchase test)
        if scenario.input_overrides.get("attempt_lifecycle_promotion"):
            from services.lifecycle.service import PolicyLifecycleService
            from services.lifecycle.schemas import PolicyPromotionRequest
            target_pol = scenario.input_overrides.get("promotion_target_policy_id", "cand_smoke_lucky")
            promo_req = PolicyPromotionRequest(
                merchant_id=scenario.merchant_id,
                candidate_policy_id=target_pol,
                expected_previous_policy_id=scenario.input_overrides.get("expected_previous_policy_id", scenario.initial_state.active_policy_id or "cand_smoke_base"),
                reason="Benchmark adversarial promotion validation",
            )
            promo_res = await PolicyLifecycleService.promote_policy(db, promo_req)
            promo_status = getattr(promo_res.promotion_status, "value", str(promo_res.promotion_status))
            promo_code = promo_res.failure_codes[0].value if promo_res.failure_codes else None

        # 1. Canonical Decision (Phase 9.1)
        dec_req = CanonicalDecisionRequest(
            merchant_id=scenario.merchant_id,
            opportunity_id=scenario.scenario_id,
            raw_prompt=scenario.buyer_context.raw_prompt,
            idempotency_key=scenario.input_overrides.get("decision_idempotency_key"),
        )
        envelope: DecisionEnvelope = await CanonicalDecisionRuntime.decide(db, dec_req)
        decision_id = envelope.decision_id

        if scenario.execution_mode == BenchmarkExecutionMode.DECISION_ONLY:
            return decision_id, None, None, False, False, promo_status, promo_code, cross_tenant_rejected, stale_state_rejected

        # If decision selected NO_OFFER or has no buyer offer, boundary execution cannot proceed
        strat = getattr(envelope.selected_policy.strategy_type, "value", envelope.selected_policy.strategy_type) if envelope.selected_policy else ""
        if not envelope.buyer_offer or strat == "NO_OFFER":
            return decision_id, None, None, False, False, promo_status, promo_code, cross_tenant_rejected, stale_state_rejected

        # Optional pre-execution cross-tenant attack test
        if scenario.input_overrides.get("test_cross_tenant_attack"):
            attacker_id = scenario.input_overrides.get("attacker_merchant_id", "merch_attacker")
            # Ensure attacker merchant exists in database to isolate tenant security check
            attacker_m = await db.get(Merchant, attacker_id)
            if not attacker_m:
                attacker_m = Merchant(
                    id=attacker_id,
                    name="Attacker Merchant",
                    currency="INR",
                    status="ACTIVE",
                )
                db.add(attacker_m)
                await db.commit()

            from services.boundary.errors import DecisionTenantViolationError
            try:
                await DecisionExecutionBoundaryService.execute_decision(
                    db=db,
                    decision_id=decision_id,
                    request=DecisionExecuteRequest(merchant_id=attacker_id),
                )
                cross_tenant_rejected = False
            except DecisionTenantViolationError:
                cross_tenant_rejected = True

        # Optional pre-execution policy retirement hook (e.g. race condition retired policy)
        if scenario.input_overrides.get("retire_policy_before_execution"):
            from domain.models import MerchantPolicyVersionRecord
            pol_id = envelope.merchant_evaluation.selected_policy_id if envelope.merchant_evaluation else "cand_golden_base"
            stmt_v = select(MerchantPolicyVersionRecord).where(
                MerchantPolicyVersionRecord.merchant_id == scenario.merchant_id,
                MerchantPolicyVersionRecord.policy_id == pol_id
            )
            v_rec = (await db.execute(stmt_v)).scalar_one_or_none()
            if not v_rec:
                v_rec = MerchantPolicyVersionRecord(
                    id=f"polver_{uuid.uuid4().hex[:12]}",
                    merchant_id=scenario.merchant_id,
                    policy_id=pol_id,
                    policy_version="merchant-policy/v1",
                    strategy_type="EXPLORATION",
                    lifecycle_status="RETIRED",
                )
                db.add(v_rec)
            else:
                v_rec.lifecycle_status = "RETIRED"
            await db.commit()

        # Optional pre-execution state mutation hook (e.g. stockout race condition)
        if scenario.input_overrides.get("mutate_inventory_before_execution") is not None:
            new_qty = scenario.input_overrides["mutate_inventory_before_execution"]
            prods = (await db.execute(select(Product).where(Product.merchant_id == scenario.merchant_id))).scalars().all()
            for p in prods:
                p.inventory_quantity = new_qty
            await db.commit()

        # 2. Execution Boundary (Phase 9.2)
        exec_idempotency_key = scenario.input_overrides.get("execution_idempotency_key")
        exec_req = DecisionExecuteRequest(
            merchant_id=scenario.merchant_id,
            idempotency_key=exec_idempotency_key,
        )
        boundary_res = await DecisionExecutionBoundaryService.execute_decision(
            db=db,
            decision_id=decision_id,
            request=exec_req,
        )
        execution_id = boundary_res.execution_id

        is_dup_exec = False
        if scenario.input_overrides.get("test_replay_execution"):
            # Replay with same idempotency key
            replay_res = await DecisionExecutionBoundaryService.execute_decision(
                db=db,
                decision_id=decision_id,
                request=exec_req,
            )
            is_dup_exec = replay_res.is_duplicate

        # Check if pre-execution mutation was safely rejected by boundary
        boundary_val = getattr(boundary_res.boundary_status, "value", boundary_res.boundary_status)
        if scenario.input_overrides.get("mutate_inventory_before_execution") is not None:
            stale_state_rejected = boundary_val in ("SAFETY_REJECTED", "DECISION_STALE", "POLICY_NOT_ACTIVE")

        # If execution was rejected (e.g. stockout, margin breach), outcome feedback stops here
        if boundary_val != "EXECUTION_COMPLETED" or not boundary_res.order_id:
            return decision_id, execution_id, None, is_dup_exec, False, promo_status, promo_code, cross_tenant_rejected, stale_state_rejected

        # 3. Simulate Payment in Phase 5
        order_stmt = select(Order).where(Order.id == boundary_res.order_id)
        order = (await db.execute(order_stmt)).scalar_one_or_none()

        if order and scenario.simulate_payment:
            pay_status = scenario.payment_status_override or "captured"
            if pay_status == "failed":
                order.status = TransactionState.FAILED.value
                pmt = Payment(
                    id=f"pay_{uuid.uuid4().hex[:12]}",
                    order_id=order.id,
                    amount_paise=boundary_res.authorized_amount_paise or 0,
                    currency="INR",
                    status="failed",
                    method="upi",
                )
                db.add(pmt)
            else:
                order.status = TransactionState.PAID.value
                pmt = Payment(
                    id=f"pay_{uuid.uuid4().hex[:12]}",
                    order_id=order.id,
                    amount_paise=boundary_res.authorized_amount_paise or 0,
                    currency="INR",
                    status="captured",
                    method="upi",
                    captured_at=datetime.now(timezone.utc),
                )
                db.add(pmt)
            await db.commit()

        # 4. Outcome Feedback (Phase 9.3)
        proc_req = OutcomeProcessRequest(
            merchant_id=scenario.merchant_id,
            execution_id=execution_id,
            idempotency_key=scenario.input_overrides.get("outcome_idempotency_key"),
        )
        outcome_resp = await OutcomeFeedbackService.process_outcome(db, proc_req)
        outcome_id = outcome_resp.outcome_id

        is_dup_outcome = False
        if scenario.input_overrides.get("test_replay_outcome"):
            replay_outcome = await OutcomeFeedbackService.process_outcome(db, proc_req)
            is_dup_outcome = replay_outcome.is_duplicate

        return decision_id, execution_id, outcome_id, is_dup_exec, is_dup_outcome, promo_status, promo_code, cross_tenant_rejected, stale_state_rejected

    @classmethod
    def _compile_terminal_expectations(cls, term: Any) -> List[BenchmarkExpectation]:
        """Convert ExpectedTerminalState fields into explicit BenchmarkExpectations."""
        exps = []
        if term.decision_mode is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_decision_mode",
                    expectation_type=ExpectationType.EXACT_STATE,
                    target_domain="decision",
                    field_path="decision_mode",
                    operator="eq",
                    expected_value=term.decision_mode,
                    failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
                    description=f"Expected decision mode to be {term.decision_mode}",
                )
            )
        if term.selected_strategy is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_selected_strategy",
                    expectation_type=ExpectationType.EXACT_VALUE,
                    target_domain="decision",
                    field_path="selected_strategy",
                    operator="eq",
                    expected_value=term.selected_strategy,
                    failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
                    description=f"Expected selected strategy to be {term.selected_strategy}",
                )
            )
        if term.execution_status is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_execution_status",
                    expectation_type=ExpectationType.EXACT_STATE,
                    target_domain="boundary",
                    field_path="boundary_status",
                    operator="eq",
                    expected_value=term.execution_status,
                    failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
                    description=f"Expected boundary status to be {term.execution_status}",
                )
            )
        if term.outcome_status is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_outcome_status",
                    expectation_type=ExpectationType.EXACT_STATE,
                    target_domain="outcome",
                    field_path="outcome_status",
                    operator="eq",
                    expected_value=term.outcome_status,
                    failure_class=FailureClass.EXPECTED_STATE_MISMATCH,
                    description=f"Expected outcome status to be {term.outcome_status}",
                )
            )
        if term.is_terminal is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_is_terminal",
                    expectation_type=ExpectationType.INVARIANT,
                    target_domain="outcome",
                    field_path="is_terminal",
                    operator="eq",
                    expected_value=term.is_terminal,
                    failure_class=FailureClass.BUSINESS_INVARIANT_FAILURE,
                    description=f"Expected outcome terminality to be {term.is_terminal}",
                )
            )
        if term.learning_eligible is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_learning_eligible",
                    expectation_type=ExpectationType.INVARIANT,
                    target_domain="outcome",
                    field_path="learning_eligible",
                    operator="eq",
                    expected_value=term.learning_eligible,
                    failure_class=FailureClass.LEARNING_INTEGRITY_FAILURE,
                    description=f"Expected learning eligibility to be {term.learning_eligible}",
                )
            )
        if term.reward_contribution_paise is not None:
            exps.append(
                BenchmarkExpectation(
                    expectation_id="term_reward_contribution",
                    expectation_type=ExpectationType.RELATIONAL,
                    target_domain="outcome",
                    field_path="reward_contribution_paise",
                    operator="eq",
                    expected_value=term.reward_contribution_paise,
                    failure_class=FailureClass.ECONOMIC_INTEGRITY_FAILURE,
                    description=f"Expected reward contribution to be {term.reward_contribution_paise}",
                )
            )
        return exps
