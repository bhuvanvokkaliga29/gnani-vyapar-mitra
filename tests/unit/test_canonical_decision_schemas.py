"""Unit Tests for Phase 9.1 Canonical Decision Runtime Schemas.

Contract: canonical-decision/v1
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType, ConfidenceLevel
from services.runtime.schemas import (
    CANONICAL_DECISION_SCHEMA_VERSION,
    DecisionMode,
    IntentSummary,
    BuyerOfferView,
    MerchantEvaluationView,
    DecisionPolicyView,
    DecisionScores,
    DecisionSafetyAudit,
    DecisionModelMetadata,
    DecisionTrace,
    CanonicalDecisionRequest,
    DecisionEnvelope
)


def test_canonical_decision_request_validation():
    """Request requires either buyer_intent or non-empty raw_prompt."""
    # 1. Missing both raises ValidationError
    with pytest.raises(ValidationError):
        CanonicalDecisionRequest(merchant_id="m1")

    # 2. Empty raw_prompt raises ValidationError
    with pytest.raises(ValidationError):
        CanonicalDecisionRequest(merchant_id="m1", raw_prompt="   ")

    # 3. Valid with raw_prompt
    req1 = CanonicalDecisionRequest(merchant_id="m1", raw_prompt="I need a travel backpack under 5000")
    assert req1.merchant_id == "m1"
    assert req1.raw_prompt == "I need a travel backpack under 5000"
    assert req1.runtime_version == CANONICAL_DECISION_SCHEMA_VERSION

    # 4. Valid with buyer_intent
    intent = BuyerIntent(
        category="travel_backpack",
        budget=BudgetConstraint(amount_paise=500000, currency="INR", budget_type=BudgetType.MAX),
        confidence=ConfidenceLevel.HIGH
    )
    req2 = CanonicalDecisionRequest(merchant_id="m1", buyer_intent=intent)
    assert req2.buyer_intent.category == "travel_backpack"

    # 5. Canonical Demo merchant fallback when prompt is omitted
    req_demo_atlas = CanonicalDecisionRequest(merchant_id="merch_atlas_travel")
    assert req_demo_atlas.raw_prompt == "High quality travel backpack for weekend travel under 7500"

    req_demo_alpha = CanonicalDecisionRequest(merchant_id="merch_alpha")
    assert req_demo_alpha.raw_prompt == "Need high quality ultralight alpine expedition travel backpack under 15000"

    req_demo_95_alpha = CanonicalDecisionRequest(merchant_id="merch_95_alpha")
    assert req_demo_95_alpha.raw_prompt == "High quality wireless noise cancelling headphones under 20000"

    # 6. Explicit prompt still overrides demo fallback
    req_override = CanonicalDecisionRequest(merchant_id="merch_atlas_travel", raw_prompt="custom search")
    assert req_override.raw_prompt == "custom search"


def test_schema_extra_fields_forbidden():
    """Extra fields forbidden across all canonical decision schemas."""
    with pytest.raises(ValidationError):
        CanonicalDecisionRequest(
            merchant_id="m1",
            raw_prompt="test",
            unexpected_field="disallowed"
        )

    with pytest.raises(ValidationError):
        DecisionScores(
            predicted_contribution_paise=1000,
            uncertainty=0.1,
            ucb_score_paise=1100,
            composite_ranking_score=0.8,
            extra_metric=99
        )

    with pytest.raises(ValidationError):
        DecisionTrace(
            total_latency_ms=15.2,
            unknown_trace_item="bad"
        )


def test_decision_envelope_full_integrity():
    """DecisionEnvelope serialization and deserialization integrity."""
    now = datetime.now(timezone.utc)
    envelope = DecisionEnvelope(
        decision_id="dec_test_001",
        merchant_id="merch_001",
        opportunity_id="opp_001",
        decision_version=CANONICAL_DECISION_SCHEMA_VERSION,
        created_at=now,
        buyer_context_key="travel_backpack:budget_high",
        intent_summary=IntentSummary(
            category="travel_backpack",
            budget_paise=500000,
            hard_requirements=["laptop_size GTE 15.6"]
        ),
        buyer_offer=BuyerOfferView(
            offer_id="off_cand_disc_10",
            strategy_type="BOUNDED_DISCOUNT",
            product_ids=["prod_1"],
            offered_price_paise=450000,
            currency="INR",
            display_discount_percent=10.0,
            rationale="10% discount on pack"
        ),
        merchant_evaluation=MerchantEvaluationView(
            selected_policy_id="cand_disc_10",
            strategy_type="BOUNDED_DISCOUNT",
            proposed_price_paise=450000,
            cogs_paise=300000,
            gross_profit_paise=150000,
            gross_margin_percent=33.33,
            predicted_contribution_paise=150000,
            uncertainty=0.15,
            ucb_score_paise=165000,
            composite_ranking_score=0.85
        ),
        selected_policy=DecisionPolicyView(
            candidate_id="cand_disc_10",
            strategy_type="BOUNDED_DISCOUNT",
            product_ids=["prod_1"],
            proposed_price_paise=450000,
            gross_profit_paise=150000,
            gross_margin_percent=33.33,
            discount_percent=10.0,
            rationale="10% discount within bounds"
        ),
        decision_mode=DecisionMode.EXPLOIT,
        decision_reason="EXPLOIT_LEARNED_PREFERENCE",
        scores=DecisionScores(
            predicted_contribution_paise=150000,
            uncertainty=0.15,
            ucb_score_paise=165000,
            composite_ranking_score=0.85
        ),
        safety_audit=DecisionSafetyAudit(
            safety_check_id="safe_chk_001",
            status="ADMISSIBLE",
            is_admissible=True
        ),
        model_metadata=DecisionModelMetadata(
            model_version="linucb_v1_merch_001",
            observation_count=25,
            feature_dimension=18,
            alpha_paise=100000
        ),
        trace=DecisionTrace(
            intent_extraction_ms=1.2,
            commerce_context_ms=2.1,
            candidate_generation_ms=3.4,
            learned_prediction_ms=1.0,
            candidate_selection_ms=0.8,
            exploration_decision_ms=1.5,
            total_latency_ms=10.0,
            candidates_generated_count=5,
            candidates_eligible_count=4
        )
    )

    dumped = envelope.model_dump(mode="json")
    assert dumped["decision_id"] == "dec_test_001"
    assert dumped["decision_mode"] == "EXPLOIT"
    assert dumped["selected_policy"]["proposed_price_paise"] == 450000

    # Reconstruct
    reconstructed = DecisionEnvelope(**dumped)
    assert reconstructed.decision_id == envelope.decision_id
    assert reconstructed.scores.ucb_score_paise == 165000
