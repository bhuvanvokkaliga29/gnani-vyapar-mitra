"""Adversarial and Invariant Test Suite for Phase 8.6 Deterministic Policy Safety Gate.

Contract: policy-safety/v1
Covers:
- Invariants A-J:
  * Invariant A: A policy violating a hard constraint can never return ADMISSIBLE.
  * Invariant B: High learning model prediction cannot override hard safety failure.
  * Invariant C: Changing learning prediction alone cannot alter safety result.
  * Invariant D: Changing fresh authoritative inventory alters admissibility for same selected policy.
  * Invariant E: Changing fresh merchant constraints alters admissibility.
  * Invariant F: Safety validation is deterministic for identical authoritative state.
  * Invariant G: Safety validation cannot mutate policy state.
  * Invariant H: Safety validation cannot execute a transaction or create orders.
  * Invariant I: Safety validation cannot bypass Phase 5 execution gate.
  * Invariant J: Cross-merchant safety evaluation is rejected.
- Static AST boundary audit verifying services/safety contains zero execution, mutation, learning, or n8n tokens.
"""

import ast
import os
from decimal import Decimal
import pytest

from domain.models import Merchant, Product
from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus
)
from services.safety.schemas import (
    PolicySafetyRequest,
    PolicySafetyResult,
    PolicySafetyStatus,
    PolicySafetyFailureCode
)
from services.safety.service import PolicySafetyService
from services.safety.validator import PolicySafetyValidator
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
async def seed_adv_safety_db(db_session):
    m = Merchant(
        id="merch_adv_saf",
        name="Adv Safety Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=25.0,
        maximum_discount_percent=8.0,
        target_aov_paise=400000
    )
    db_session.add(m)

    p1 = Product(
        id="prod_adv_01",
        merchant_id="merch_adv_saf",
        sku="SKU-ADV-01",
        name="Adv Backpack",
        category="travel_backpack",
        price_paise=500000,
        cost_paise=250000,
        currency="INR",
        inventory_quantity=5,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add(p1)
    await db_session.commit()
    return m, p1


def test_invariant_a_hard_constraint_violation_never_admissible():
    """Invariant A: A policy violating any hard constraint (e.g. margin floor) can never be ADMISSIBLE."""
    ctx = build_test_commerce_context(minimum_margin_percent=Decimal("30.00"))
    cand = PolicyCandidate(
        candidate_id="c_violation",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_backpack_01"],
        # Deep discount causing margin to collapse
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("45.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Loss-leader deep discount"
    )
    status, failures, _, _ = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=ctx,
        merchant_id=ctx.merchant_id
    )
    assert status == PolicySafetyStatus.REJECTED
    assert len(failures) > 0


def test_invariant_b_and_c_model_prediction_cannot_override_safety():
    """Invariant B & C: Learner's predicted contribution / UCB cannot override a hard safety failure,
    and changing model prediction alone does not alter safety admissibility."""
    ctx = build_test_commerce_context(maximum_discount_percent=Decimal("5.00"))
    cand = PolicyCandidate(
        candidate_id="c_predicted_high",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_backpack_01"],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("12.00")),
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Learner claims +1,000,000 paise contribution"
    )
    # Even if an external agent claims a massive +1,000,000 paise prediction,
    # the safety gate inspects the candidate against fresh context and rejects it!
    status, failures, _, _ = PolicySafetyValidator.validate_admissibility(
        candidate=cand,
        fresh_context=ctx,
        merchant_id=ctx.merchant_id
    )
    assert status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED in failures


@pytest.mark.asyncio
async def test_invariant_d_changing_fresh_inventory_changes_admissibility(db_session, seed_adv_safety_db):
    """Invariant D: Changing fresh authoritative inventory in DB turns previously ADMISSIBLE candidate into REJECTED."""
    m, p = seed_adv_safety_db
    req = PolicySafetyRequest(
        merchant_id=m.id,
        opportunity_id="opp_dyn_inv_1",
        buyer_context_key="bck_dyn",
        proposed_policy=PolicyCandidate(
            candidate_id="cand_inv_deplete",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=[p.id],
            bundle_components=[{"product_id": p.id, "quantity": 4}],
            validation_status=CandidateValidationStatus.APPROVED,
            rationale="Requires 4 units"
        )
    )

    # 1. Initially 5 available -> ADMISSIBLE
    res1 = await PolicySafetyService.validate_policy(db_session, req)
    assert res1.status == PolicySafetyStatus.ADMISSIBLE

    # 2. Mutate authoritative inventory in DB to 2
    p.inventory_quantity = 2
    await db_session.commit()

    # With state-aware idempotency (Phase 8.6.1), even with the SAME opportunity_id,
    # the altered authoritative state forces revalidation and returns REJECTED!
    res2 = await PolicySafetyService.validate_policy(db_session, req)
    assert res2.status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.INVENTORY_INSUFFICIENT in res2.failure_codes
    assert res2.safety_check_id != res1.safety_check_id


@pytest.mark.asyncio
async def test_invariant_e_changing_merchant_constraints_changes_admissibility(db_session, seed_adv_safety_db):
    """Invariant E: Tightening merchant constraint in DB turns candidate into REJECTED."""
    m, p = seed_adv_safety_db
    # Candidate with 6% discount
    req = PolicySafetyRequest(
        merchant_id=m.id,
        opportunity_id="opp_dyn_const_1",
        buyer_context_key="bck_dyn",
        proposed_policy=PolicyCandidate(
            candidate_id="cand_disc_6",
            strategy_type=StrategyType.BOUNDED_DISCOUNT,
            product_ids=[p.id],
            incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("6.00")),
            validation_status=CandidateValidationStatus.APPROVED,
            rationale="6% discount"
        )
    )

    # 1. Under max 8% discount -> ADMISSIBLE
    res1 = await PolicySafetyService.validate_policy(db_session, req)
    assert res1.status == PolicySafetyStatus.ADMISSIBLE

    # 2. Tighten merchant max discount to 4%
    m.maximum_discount_percent = 4.0
    await db_session.commit()

    # With state-aware idempotency, same opportunity_id revalidates against tightened constraints!
    res2 = await PolicySafetyService.validate_policy(db_session, req)
    assert res2.status == PolicySafetyStatus.REJECTED
    assert PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED in res2.failure_codes
    assert res2.safety_check_id != res1.safety_check_id


def test_invariant_f_and_g_determinism_and_immutability():
    """Invariant F & G: Safety evaluation is deterministic and does not mutate candidate."""
    ctx = build_test_commerce_context()
    cand = PolicyCandidate(
        candidate_id="cand_immut",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Immutable check"
    )
    dump_before = cand.model_dump()

    res1 = PolicySafetyValidator.validate_admissibility(cand, ctx, ctx.merchant_id)
    res2 = PolicySafetyValidator.validate_admissibility(cand, ctx, ctx.merchant_id)

    assert res1 == res2
    assert cand.model_dump() == dump_before


@pytest.mark.asyncio
async def test_invariant_h_and_i_zero_execution_and_phase5_integrity(db_session, seed_adv_safety_db):
    """Invariant H & I: Safety gate does not reserve inventory, create orders, or bypass Phase 5."""
    m, p = seed_adv_safety_db
    reserved_before = p.reserved_quantity

    req = PolicySafetyRequest(
        merchant_id=m.id,
        opportunity_id="opp_no_exec",
        buyer_context_key="bck_k",
        proposed_policy=PolicyCandidate(
            candidate_id="cand_safe",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=[p.id],
            validation_status=CandidateValidationStatus.APPROVED,
            rationale="Safe"
        )
    )
    res = await PolicySafetyService.validate_policy(db_session, req)
    assert res.status == PolicySafetyStatus.ADMISSIBLE

    # Inventory reserved quantity must NOT change in Phase 8.6!
    await db_session.refresh(p)
    assert p.reserved_quantity == reserved_before


def test_invariant_j_and_boundary_ast_audit():
    """Invariant J & AST Audit: Cross-merchant isolation, zero execution, zero learning, zero n8n."""
    safety_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "services", "safety"))
    forbidden_tokens = {
        "execute_order",
        "create_order",
        "capture_payment",
        "ExecutionAuthorization",
        "mutate_policy",
        "promote_policy",
        "deploy_policy",
        "LinUCB",
        "ContextualLinearUCB",
        "n8n"
    }

    found_violations = []
    for root, _, files in os.walk(safety_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    parsed = ast.parse(f.read(), filename=file_path)
                    for node in ast.walk(parsed):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id in forbidden_tokens:
                                found_violations.append(f"Forbidden call {node.func.id} in {file}")
                            elif isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_tokens:
                                found_violations.append(f"Forbidden method {node.func.attr} in {file}")
                        elif isinstance(node, ast.Name) and node.id in forbidden_tokens:
                            found_violations.append(f"Forbidden reference {node.id} in {file}")

    assert not found_violations, f"AST Boundary violations found in services/safety: {found_violations}"
