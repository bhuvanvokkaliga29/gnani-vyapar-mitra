"""Unit tests for ObjectiveAggregator and denominator rules."""

import pytest
from services.experiments.schemas import VariantType
from services.learning.schemas import EvidenceSource, LearningOutcomeType
from services.reward.schemas import (
    PolicyOpportunityReward,
    RewardState,
    ObjectiveMetricType
)
from services.reward.aggregator import ObjectiveAggregator
from services.reward.errors import (
    ZeroDenominatorError,
    RewardAttributionError
)


def make_reward(
    idx: int,
    contrib_paise: int,
    is_admissible: bool = True,
    state: RewardState = RewardState.REWARD_ELIGIBLE,
    merchant_id: str = "merch_atlas",
    policy_id: str = "p_treat"
) -> PolicyOpportunityReward:
    return PolicyOpportunityReward(
        reward_id=f"rwd_{idx}",
        merchant_id=merchant_id,
        opportunity_id=f"exp_01:scen_{idx}:TREATMENT",
        buyer_context_key="bck_backpack",
        policy_id=policy_id,
        experiment_id="exp_01",
        variant=VariantType.TREATMENT,
        evidence_id=f"evi_{idx}",
        evidence_source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION if contrib_paise > 0 else LearningOutcomeType.NO_SELECTION,
        reward_state=state,
        is_admissible=is_admissible,
        reward_contribution_paise=contrib_paise,
        realized_revenue_paise=contrib_paise * 2 if contrib_paise > 0 else 0,
        realized_cogs_paise=contrib_paise if contrib_paise > 0 else 0,
        idempotency_key=f"idem_{idx}"
    )


def test_aggregator_denominator_includes_all_eligible_opportunities():
    """CRITICAL: Denominator must be ALL eligible opportunities, NOT just converted ones!"""
    # 10 opportunities total: 2 converted (Rs 1,000 each = 100,000 paise), 8 non-purchases (0 paise)
    rewards = [
        make_reward(1, 100000),
        make_reward(2, 100000),
        make_reward(3, 0, state=RewardState.REWARD_ZERO),
        make_reward(4, 0, state=RewardState.REWARD_ZERO),
        make_reward(5, 0, state=RewardState.REWARD_ZERO),
        make_reward(6, 0, state=RewardState.REWARD_ZERO),
        make_reward(7, 0, state=RewardState.REWARD_ZERO),
        make_reward(8, 0, state=RewardState.REWARD_ZERO),
        make_reward(9, 0, state=RewardState.REWARD_ZERO),
        make_reward(10, 0, state=RewardState.REWARD_ZERO),
    ]

    obj = ObjectiveAggregator.aggregate_objective(rewards)

    # Denominator must be 10 (NOT 2!)
    assert obj.eligible_opportunity_count == 10
    assert obj.total_contribution_paise == 200000  # Rs 2,000
    # Expected contribution per shopper: 200,000 / 10 = 20,000 paise (Rs 200)
    assert obj.contribution_per_shopper_paise == 20000
    assert obj.contribution_per_shopper_decimal == 20000.0
    assert obj.successful_payment_count == 2
    assert obj.successful_payment_rate == 0.2


def test_aggregator_excludes_ineligible_evidence_from_denominator():
    """Ineligible evidence is EXCLUDED from denominator, NOT silently converted to zero!"""
    # 5 opportunities: 2 valid conversions (100k paise each), 1 valid zero (0 paise), 2 INELIGIBLE (guardrail breached)
    rewards = [
        make_reward(1, 100000),
        make_reward(2, 100000),
        make_reward(3, 0, state=RewardState.REWARD_ZERO),
        make_reward(4, 0, is_admissible=False, state=RewardState.REWARD_INELIGIBLE),
        make_reward(5, 0, is_admissible=False, state=RewardState.REWARD_INELIGIBLE),
    ]

    obj = ObjectiveAggregator.aggregate_objective(rewards)

    assert obj.total_opportunities_evaluated == 5
    assert obj.eligible_opportunity_count == 3  # Excludes the 2 ineligible ones!
    assert obj.ineligible_opportunity_count == 2
    assert obj.total_contribution_paise == 200000
    # 200,000 / 3 = 66,666.6667 -> 66,667 paise
    assert obj.contribution_per_shopper_paise == 66667


def test_aggregator_zero_denominator_raises_error():
    """When all opportunities are ineligible, denominator is 0 -> raises ZeroDenominatorError."""
    rewards = [
        make_reward(1, 0, is_admissible=False, state=RewardState.REWARD_INELIGIBLE),
        make_reward(2, 0, is_admissible=False, state=RewardState.REWARD_INELIGIBLE),
    ]

    with pytest.raises(ZeroDenominatorError):
        ObjectiveAggregator.aggregate_objective(rewards)


def test_aggregator_rejects_cross_tenant_mixing():
    """Aggregator strictly prevents mixing Merchant A and Merchant B rewards."""
    rewards = [
        make_reward(1, 100000, merchant_id="merch_alpha"),
        make_reward(2, 100000, merchant_id="merch_beta"),
    ]

    with pytest.raises(RewardAttributionError):
        ObjectiveAggregator.aggregate_objective(rewards)
