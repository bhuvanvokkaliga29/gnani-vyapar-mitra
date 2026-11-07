"""Unit tests for Phase 8.2 Reward and Objective schemas and contracts."""

import pytest
from pydantic import ValidationError
from services.experiments.schemas import VariantType
from services.learning.schemas import EvidenceSource, LearningOutcomeType
from services.reward.schemas import (
    PolicyOpportunityReward,
    AggregatedRewardObjective,
    RewardState,
    ObjectiveMetricType
)


def test_opportunity_reward_schema_valid():
    """PolicyOpportunityReward conforms to merchant-reward/v1 contract."""
    reward = PolicyOpportunityReward(
        reward_id="rwd_01",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        merchant_id="merch_atlas",
        opportunity_id="exp_01:scen_01:TREATMENT",
        buyer_context_key="bck_test",
        policy_id="p_treat",
        policy_version="merchant-policy/v1",
        experiment_id="exp_01",
        experiment_version="policy-experiment/v1",
        variant=VariantType.TREATMENT,
        evidence_id="evi_01",
        evidence_source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        reward_state=RewardState.REWARD_ELIGIBLE,
        is_admissible=True,
        realized_revenue_paise=349900,
        realized_cogs_paise=170000,
        reward_contribution_paise=179900,
        margin_percent=51.41,
        idempotency_key="rwd_idem_01"
    )

    assert reward.reward_version == "merchant-reward/v1"
    assert reward.formula_version == "contribution-formula/v1"
    assert reward.reward_contribution_paise == 179900


def test_opportunity_reward_forbids_extra_fields():
    """PolicyOpportunityReward strictly forbids extra fields."""
    with pytest.raises(ValidationError):
        PolicyOpportunityReward(
            reward_id="rwd_02",
            merchant_id="merch_atlas",
            opportunity_id="exp_01:scen_02:CONTROL",
            buyer_context_key="bck_test",
            policy_id="p_ctrl",
            experiment_id="exp_01",
            variant=VariantType.CONTROL,
            evidence_id="evi_02",
            evidence_source=EvidenceSource.SIMULATED,
            outcome_type=LearningOutcomeType.NO_SELECTION,
            reward_state=RewardState.REWARD_ZERO,
            is_admissible=True,
            idempotency_key="idem_02",
            unauthorized_bandit_weight=0.85  # FORBIDDEN!
        )


def test_aggregated_objective_schema_valid():
    """AggregatedRewardObjective encapsulates the primary learning objective."""
    obj = AggregatedRewardObjective(
        objective_id="obj_01",
        objective_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        merchant_id="merch_atlas",
        policy_id="p_treat",
        total_opportunities_evaluated=10,
        eligible_opportunity_count=10,
        total_contribution_paise=1799000,
        contribution_per_shopper_paise=179900,
        contribution_per_shopper_decimal=179900.0,
        aggregation_key="agg_key"
    )

    assert obj.contribution_per_shopper_paise == 179900
    assert obj.eligible_opportunity_count == 10
