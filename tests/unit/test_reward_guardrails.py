"""Unit tests for guardrail admissibility constraints in the reward layer."""

from datetime import datetime, timezone
import pytest
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus,
    EvidenceGuardrailSummary
)
from services.reward.calculator import RewardSignalEvaluator
from services.reward.aggregator import ObjectiveAggregator
from services.reward.schemas import RewardState


def test_guardrail_breach_disqualifies_apparent_high_reward():
    """Admissibility Constraint: High revenue/contribution achieved by breaching margin floor is disqualified.
    
    Guardrails are NOT soft penalties; they strictly zero contribution, stay in denominator, and flag safety violation.
    """
    evidence_breached = PolicyLearningEvidence(
        evidence_id="evi_guard_breached",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas",
        experiment_id="exp_01",
        experiment_observation_id="obs_01",
        scenario_id="scen_01",
        policy_id="p_treat_predatory",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=900000,       # High apparent revenue!
        expected_contribution_paise=100000,  # Positive contribution
        margin_percent=11.11,               # Breached 40% margin floor!
        guardrail_results=[
            EvidenceGuardrailSummary(
                guardrail_type="MIN_MARGIN_PERCENT",
                threshold_value=40.0,
                observed_value=11.11,
                passed=False,
                detail="Margin 11.11% violates floor 40.0%"
            )
        ],
        evidence_status=EvidenceQualityStatus.GUARDRAIL_FAILURE,
        learning_eligible=False,
        eligibility_reasons=["Guardrail failure: Margin 11.11% violates floor 40.0%"],
        aggregation_key="agg_01",
        idempotency_key="idem_guard_breached",
        observed_at=datetime.now(timezone.utc)
    )

    reward = RewardSignalEvaluator.evaluate_opportunity(evidence_breached)

    # REWARD_GUARDRAIL_VIOLATION: Retained in denominator with 0 contribution, flagged as safety violation
    assert reward.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION
    assert reward.is_admissible is True
    assert reward.is_safety_violation is True
    assert reward.reward_contribution_paise == 0
    assert "guardrail" in reward.inadmissibility_reasons[0].lower()


def test_guardrail_failures_remain_in_denominator_preventing_selection_bias():
    """Anti-Selection Bias: 20 guardrail failures in 100 opportunities MUST NOT vanish from denominator.
    
    If excluded: 800,000 / 80 = 10,000 paise (artificially inflated).
    When retained: 800,000 / 100 = 8,000 paise (correctly diluted) + is_policy_admissible = False.
    """
    rewards = []
    # 10 successes (80,000 paise each = 800,000 total)
    for i in range(10):
        rewards.append(
            RewardSignalEvaluator.evaluate_opportunity(
                PolicyLearningEvidence(
                    evidence_id=f"evi_succ_{i}",
                    evidence_version="merchant-learning/v1",
                    merchant_id="merch_atlas",
                    experiment_id="exp_01",
                    experiment_observation_id=f"obs_succ_{i}",
                    scenario_id=f"scen_succ_{i}",
                    policy_id="p_treat",
                    variant=VariantType.TREATMENT,
                    buyer_context_key="bck_test",
                    source=EvidenceSource.SIMULATED,
                    outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
                    sample_size=1,
                    is_selected=True,
                    expected_revenue_paise=160000,
                    expected_contribution_paise=80000,
                    margin_percent=50.0,
                    evidence_status=EvidenceQualityStatus.VALID,
                    learning_eligible=True,
                    aggregation_key="agg_01",
                    idempotency_key=f"idem_succ_{i}",
                    observed_at=datetime.now(timezone.utc)
                )
            )
        )
    # 70 non-purchases (0 paise)
    for i in range(70):
        rewards.append(
            RewardSignalEvaluator.evaluate_opportunity(
                PolicyLearningEvidence(
                    evidence_id=f"evi_zero_{i}",
                    evidence_version="merchant-learning/v1",
                    merchant_id="merch_atlas",
                    experiment_id="exp_01",
                    experiment_observation_id=f"obs_zero_{i}",
                    scenario_id=f"scen_zero_{i}",
                    policy_id="p_treat",
                    variant=VariantType.TREATMENT,
                    buyer_context_key="bck_test",
                    source=EvidenceSource.SIMULATED,
                    outcome_type=LearningOutcomeType.NO_SELECTION,
                    sample_size=1,
                    is_selected=False,
                    expected_revenue_paise=0,
                    expected_contribution_paise=0,
                    evidence_status=EvidenceQualityStatus.VALID,
                    learning_eligible=True,
                    aggregation_key="agg_01",
                    idempotency_key=f"idem_zero_{i}",
                    observed_at=datetime.now(timezone.utc)
                )
            )
        )
    # 20 guardrail failures (0 paise, safety violation)
    for i in range(20):
        rewards.append(
            RewardSignalEvaluator.evaluate_opportunity(
                PolicyLearningEvidence(
                    evidence_id=f"evi_fail_{i}",
                    evidence_version="merchant-learning/v1",
                    merchant_id="merch_atlas",
                    experiment_id="exp_01",
                    experiment_observation_id=f"obs_fail_{i}",
                    scenario_id=f"scen_fail_{i}",
                    policy_id="p_treat",
                    variant=VariantType.TREATMENT,
                    buyer_context_key="bck_test",
                    source=EvidenceSource.SIMULATED,
                    outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
                    sample_size=1,
                    is_selected=True,
                    expected_revenue_paise=100000,
                    expected_contribution_paise=5000,
                    margin_percent=5.0,  # Breached floor
                    evidence_status=EvidenceQualityStatus.GUARDRAIL_FAILURE,
                    learning_eligible=False,
                    eligibility_reasons=["Margin 5% violates 40% floor"],
                    aggregation_key="agg_01",
                    idempotency_key=f"idem_fail_{i}",
                    observed_at=datetime.now(timezone.utc)
                )
            )
        )

    obj = ObjectiveAggregator.aggregate_objective(rewards)

    # Denominator must be ALL 100 evaluated opportunities (NOT 80!)
    assert obj.total_opportunities_evaluated == 100
    assert obj.eligible_opportunity_count == 100
    assert obj.guardrail_violation_count == 20
    assert obj.is_policy_admissible is False  # Disqualified due to violations!
    assert obj.total_contribution_paise == 800000
    # Contribution per shopper is 800,000 / 100 = 8,000 paise (NOT 10,000!)
    assert obj.contribution_per_shopper_paise == 8000
    assert obj.contribution_per_shopper_decimal == 8000.0
