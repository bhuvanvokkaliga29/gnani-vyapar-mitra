"""Comprehensive hardening & invariant verification tests for Phase 4."""

import ast
import os
from decimal import Decimal
import pytest
from domain.commerce_schemas import ProductResponse
from domain.intent_schemas import BuyerIntent, BudgetConstraint, AttributePreference, ExclusionConstraint
from services.policy.agent import MerchantPolicyAgent
from services.policy.schemas import (
    PolicyCandidate,
    PolicyEvidence,
    PolicyScore,
    StrategyType,
    CandidateValidationStatus,
    ProposalStatus
)
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.fixture
def agent():
    return MerchantPolicyAgent()


@pytest.fixture
def context():
    return build_test_commerce_context()


# =============================================================================
# REFINEMENT 1: MANDATORY NO_OFFER FALLBACK
# =============================================================================

def test_mandatory_no_offer_all_over_budget(agent, context):
    """When all candidate products exceed buyer budget, return valid NO_OFFER policy."""
    # Impossible tiny budget of Rs 100 (10000 paise)
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=10000, constraint_type="HARD")
    )
    proposal = agent.generate_policy(intent, context)

    assert proposal.status == ProposalStatus.VALID
    assert proposal.selected_candidate is not None
    assert proposal.selected_candidate.strategy_type == StrategyType.NO_OFFER
    assert proposal.selected_candidate.validation_status == CandidateValidationStatus.APPROVED
    assert proposal.selected_candidate.product_ids == []
    assert "OVER_BUDGET" in proposal.selected_candidate.rationale or "OVER_BUDGET" in proposal.audit_trail.get("step_trace", [])


def test_mandatory_no_offer_all_below_margin_floor(agent, context):
    """When merchant margin floor is set so high (e.g. 99%) that no candidate qualifies, return NO_OFFER."""
    strict_context = build_test_commerce_context()
    strict_context.constraints["minimum_margin_percent"] = 99.0  # Impossible 99% margin floor

    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=1000000)
    )
    proposal = agent.generate_policy(intent, strict_context)

    assert proposal.status == ProposalStatus.VALID
    assert proposal.selected_candidate is not None
    assert proposal.selected_candidate.strategy_type == StrategyType.NO_OFFER
    assert "MARGIN_TOO_LOW" in proposal.selected_candidate.rationale


def test_mandatory_no_offer_all_out_of_stock(agent, context):
    """When all catalog items have zero available stock, return clean NO_OFFER."""
    oos_context = build_test_commerce_context()
    for p in oos_context.products:
        p.available_to_sell = 0

    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=1000000)
    )
    proposal = agent.generate_policy(intent, oos_context)

    assert proposal.status == ProposalStatus.VALID
    assert proposal.selected_candidate is not None
    assert proposal.selected_candidate.strategy_type == StrategyType.NO_OFFER


def test_mandatory_no_offer_all_violating_exclusions(agent, context):
    """When buyer excludes all materials present in catalog, return NO_OFFER."""
    intent = BuyerIntent(
        category="travel_backpack",
        exclusions=[
            ExclusionConstraint(attribute="material", excluded_value="nylon"),
            ExclusionConstraint(attribute="material", excluded_value="cordura"),
            ExclusionConstraint(attribute="material", excluded_value="polyester"),
            ExclusionConstraint(attribute="material", excluded_value="leather"),
            ExclusionConstraint(attribute="material", excluded_value="canvas")
        ]
    )
    proposal = agent.generate_policy(intent, context)

    assert proposal.status == ProposalStatus.VALID
    assert proposal.selected_candidate is not None
    assert proposal.selected_candidate.strategy_type == StrategyType.NO_OFFER


def test_mandatory_no_offer_mixed_failures(agent, context):
    """When generated candidates fail for different reasons, zero valid candidates returns NO_OFFER."""
    # Set high discount ceiling and tight margin floor
    mixed_context = build_test_commerce_context()
    mixed_context.constraints["minimum_margin_percent"] = 70.0  # High margin floor eliminates packs

    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(max_amount_paise=400000, constraint_type="HARD")
    )
    proposal = agent.generate_policy(intent, mixed_context)

    assert proposal.status == ProposalStatus.VALID
    assert proposal.selected_candidate is not None
    assert proposal.selected_candidate.strategy_type == StrategyType.NO_OFFER


# =============================================================================
# REFINEMENT 8: HARD CANDIDATE BOUNDING IN APPLICATION LAYER
# =============================================================================

def test_candidate_bounding_zero_candidates(agent):
    """Application layer safely handles empty candidate list."""
    bounded = agent._bound_and_sanitize_candidates([])
    assert len(bounded) == 1
    assert bounded[0].strategy_type == StrategyType.NO_OFFER


def test_candidate_bounding_upper_limit_5(agent):
    """Application layer hard truncates any candidate list > 5 to exactly 5."""
    many_candidates = [
        PolicyCandidate(
            candidate_id=f"cand_test_{i}",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=[f"prod_sku_{i}"],
            rationale=f"Candidate {i}",
            confidence="HIGH"
        )
        for i in range(50)
    ]
    bounded = agent._bound_and_sanitize_candidates(many_candidates)
    assert len(bounded) == 5


def test_candidate_bounding_duplicate_deduplication(agent):
    """Application layer deduplicates candidates with identical strategy signatures."""
    dup_candidates = [
        PolicyCandidate(
            candidate_id="cand_1",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=["prod_01"],
            rationale="Original",
            confidence="HIGH"
        ),
        PolicyCandidate(
            candidate_id="cand_2",
            strategy_type=StrategyType.SINGLE_PRODUCT,
            product_ids=["prod_01"],
            rationale="Duplicate",
            confidence="HIGH"
        )
    ]
    bounded = agent._bound_and_sanitize_candidates(dup_candidates)
    assert len(bounded) == 1
    assert bounded[0].candidate_id == "cand_1"


# =============================================================================
# REFINEMENT 2 & 3: PROVENANCE & SNAPSHOT SEMANTICS
# =============================================================================

def test_proposal_provenance_and_snapshot_metadata(agent, context):
    """Every generated proposal contains complete audit provenance and snapshot metadata."""
    intent = BuyerIntent(category="travel_backpack")
    proposal = agent.generate_policy(intent, context)

    assert proposal.policy_version == "merchant-policy/v1"
    assert proposal.prompt_version == "merchant-policy-agent/v1"
    assert proposal.intent_version == "buyer-intent/v1"
    assert proposal.context_version == "commerce-context/v1"
    assert proposal.validator_version == "deterministic-validator/v1"
    assert proposal.objective == context.business_objective
    assert proposal.is_provisional is True
    assert proposal.context_snapshot_at is not None
    assert proposal.generation_timestamp is not None


def test_context_snapshot_provisional_semantics(agent, context):
    """Proposal is explicitly provisional; changing inventory later requires revalidation."""
    intent = BuyerIntent(category="travel_backpack")
    proposal = agent.generate_policy(intent, context)

    # Initial proposal approved
    assert proposal.status == ProposalStatus.APPROVED_FOR_EVALUATION
    assert proposal.is_provisional is True

    # Suppose context state changes (e.g., inventory depleted)
    stale_product_id = proposal.selected_candidate.product_ids[0]
    updated_context = build_test_commerce_context()
    for p in updated_context.products:
        if p.id == stale_product_id:
            p.available_to_sell = 0

    # Revalidation against fresh state catches the changed reality
    revalidated = agent.validator.validate_candidate(proposal.selected_candidate, intent, updated_context)
    assert revalidated.validation_status == CandidateValidationStatus.REJECTED
    assert "OUT_OF_STOCK" in revalidated.rejection_reasons


# =============================================================================
# REFINEMENT 4: STRICT EVIDENCE-GROUNDING CONTRACT
# =============================================================================

def test_strict_evidence_grounding_validation():
    """PolicyEvidence schema forbids ungrounded or fabricated evidence sources."""
    # Valid evidence type
    valid_ev = PolicyEvidence(
        evidence_type="merchant_attribute",
        field="minimum_margin_percent",
        description="Margin is 40%"
    )
    assert valid_ev.evidence_type == "merchant_attribute"

    # Invalid / fabricated evidence source
    with pytest.raises(ValueError):
        PolicyEvidence(
            evidence_type="market_survey_speculation",
            field="ai_buyer_preference",
            description="AI buyers prefer this color"
        )


# =============================================================================
# REFINEMENT 5: RANKING-SCORE SEMANTICS (NO CONVERSION PROBABILITY)
# =============================================================================

def test_ranking_score_semantics_no_conversion_probability(agent, context):
    """Scores are strictly ranking metrics; no conversion probability fields exist."""
    intent = BuyerIntent(category="travel_backpack")
    proposal = agent.generate_policy(intent, context)

    for cand in proposal.candidates:
        if cand.score:
            # Must not contain conversion probability
            assert not hasattr(cand.score, "conversion_probability")
            assert not hasattr(cand.score, "expected_conversion_rate")
            assert not hasattr(cand.score, "purchase_probability")
            # Composite score is bounded [0.0, 1.0]
            assert 0.0 <= cand.score.composite_score <= 1.0


# =============================================================================
# REFINEMENT 9: ARCHITECTURAL BOUNDARY AUDIT
# =============================================================================

def test_architectural_boundary_no_razorpay_in_policy():
    """Inspect all Python files in services/policy/ ensuring ZERO Razorpay imports or spend calls."""
    policy_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "policy")

    forbidden_terms = [
        "RazorpayClient",
        "services.razorpay",
        "create_order",
        "orders.create",
        "payment_link",
        "capture_payment"
    ]

    for root, _, files in os.walk(policy_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                for term in forbidden_terms:
                    assert term not in content, (
                        f"CRITICAL ARCHITECTURAL VIOLATION: '{term}' found in {filepath}. "
                        "The Policy Agent must have ZERO Razorpay execution capabilities!"
                    )
