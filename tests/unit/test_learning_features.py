"""Unit tests for Phase 8.4 Feature Extraction & Schema Contract."""

import math
import pytest
from services.learning.features import (
    PolicyFeatureExtractor,
    FEATURE_DIMENSION,
    FEATURE_SCHEMA_VERSION,
    FEATURE_NAMES
)
from services.learning.model_errors import IncompatibleFeatureSchemaError
from domain.intent_schemas import BuyerIntent, BudgetConstraint, BudgetType, AttributeRequirement, OperatorType
from services.policy.schemas import PolicyCandidate, StrategyType, IncentiveProposal, CandidateEconomics
from decimal import Decimal


def test_feature_dimension_and_schema_version():
    """Verify exact 19 dimensions and schema contract."""
    assert len(FEATURE_NAMES) == FEATURE_DIMENSION == 19
    assert FEATURE_SCHEMA_VERSION == "feature-schema/v1"


def test_empty_input_deterministic_fallback():
    """Extracting with None inputs must succeed, providing a finite deterministic vector."""
    x = PolicyFeatureExtractor.extract()
    assert len(x) == 19
    assert x[0] == 1.0  # bias
    assert not any(math.isnan(v) or math.isinf(v) for v in x)


def test_identical_inputs_produce_identical_vectors():
    """Determinism check: same intent and candidate produce identical vector."""
    intent = BuyerIntent(
        category="backpack",
        use_case="travel",
        budget=BudgetConstraint(budget_type=BudgetType.MAX, max_amount_paise=350000),
        quantity=2,
        requirements=[AttributeRequirement(attribute="feature", operator=OperatorType.CONTAINS, value="water resistant")]
    )
    candidate = PolicyCandidate(
        candidate_id="cand_1",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["prod_1", "prod_2"],
        bundle_components=[{"product_id": "prod_1"}, {"product_id": "prod_2"}],
        incentive=IncentiveProposal(incentive_type="discount", discount_percent=Decimal("10.0")),
        rationale="Value proposition"
    )

    x1 = PolicyFeatureExtractor.extract(intent=intent, candidate=candidate)
    x2 = PolicyFeatureExtractor.extract(intent=intent, candidate=candidate)

    assert x1 == x2
    assert x1[0] == 1.0  # bias
    assert x1[1] == 0.50  # MID budget tier
    assert x1[3] == 1.0   # bulk quantity > 1
    assert x1[5] == 1.0   # hard requirements present
    assert x1[7] == 1.0   # COMPLEMENTARY_BUNDLE
    assert x1[12] == 0.10  # 10% discount
    assert x1[15] == 0.50 * 0.10  # interaction: budget_tier * discount


def test_anti_leakage_post_decision_fields_not_present():
    """Verify that post-outcome terms are forbidden from feature names."""
    forbidden = ["payment", "captured", "revenue_realized", "cogs_realized", "refund", "conversion", "outcome"]
    for name in FEATURE_NAMES:
        for f in forbidden:
            assert f not in name, f"Leakage detected! '{name}' contains forbidden keyword '{f}'"
