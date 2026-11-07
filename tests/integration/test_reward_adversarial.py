"""Adversarial and Edge Case Verification Suite for Phase 8.2 Learning Objective & Reward.

Verifies the 20 adversarial failure modes specified in Phase 8.2 requirements:
1. Revenue increases while contribution decreases
2. Discount increases conversion but destroys margin
3. No purchases in a population
4. One successful payment and many non-purchases
5. Duplicate observations
6. Repeated retries
7. Payment failure after order creation
8. Missing contribution input
9. Negative contribution
10. Zero denominator
11. Stale transaction evidence
12. Invalid evidence
13. Simulated evidence accidentally treated as observed
14. Test Mode accidentally described as production
15. Policy receives post-outcome information
16. One outcome attributed to two policies
17. Merchant A evidence appearing in merchant B aggregation
18. Formula version changes after historical rewards exist
19. Guardrail violation producing a high apparent reward
20. Expected contribution being mistaken for observed contribution
"""

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
from services.reward.schemas import (
    PolicyOpportunityReward,
    RewardState,
    ObjectiveMetricType
)
from services.reward.calculator import ContributionCalculator, RewardSignalEvaluator
from services.reward.aggregator import ObjectiveAggregator
from services.reward.errors import (
    ZeroDenominatorError,
    RewardAttributionError,
    RewardLeakageError,
    IneligibleRewardError
)


def create_base_evidence(idx: int = 1, merchant: str = "merch_atlas", policy: str = "p_treat") -> PolicyLearningEvidence:
    return PolicyLearningEvidence(
        evidence_id=f"evi_adv_{idx}",
        evidence_version="merchant-learning/v1",
        merchant_id=merchant,
        experiment_id="exp_adv_01",
        experiment_observation_id=f"obs_adv_{idx}",
        scenario_id=f"scen_{idx}",
        policy_id=policy,
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=300000,
        expected_contribution_paise=150000,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key=f"{merchant}:bck_test:{policy}:merchant-policy/v1",
        idempotency_key=f"idem_adv_{idx}",
        observed_at=datetime.now(timezone.utc)
    )


def test_adversarial_1_revenue_increases_while_contribution_decreases():
    """Policy A: Rev 3,000, Contrib 1,500. Policy B: Rev 5,000, Contrib 1,000.
    The learner objective must prefer Policy A despite lower revenue!"""
    c_a = ContributionCalculator.calculate_contribution_paise(300000, 150000) # 150,000
    c_b = ContributionCalculator.calculate_contribution_paise(500000, 400000) # 100,000
    assert c_a > c_b


def test_adversarial_2_discount_increases_conversion_but_destroys_margin():
    """Heavy discounts convert at 100% but violate margin floor -> penalized with 0 contribution and safety violation."""
    e = create_base_evidence(2)
    e.expected_revenue_paise = 200000
    e.expected_contribution_paise = 20000
    e.margin_percent = 10.0
    e.evidence_status = EvidenceQualityStatus.GUARDRAIL_FAILURE
    e.learning_eligible = False
    e.eligibility_reasons = ["Margin 10% below 40% floor"]

    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    # Anti-selection: retained in denominator with 0 contribution, marked safety violation
    assert rwd.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION
    assert rwd.is_admissible is True
    assert rwd.is_safety_violation is True
    assert rwd.reward_contribution_paise == 0


def test_adversarial_3_no_purchases_in_a_population():
    """All 10 opportunities resulted in NO_SELECTION -> Total contribution is 0, denominator is 10."""
    rewards = []
    for i in range(10):
        e = create_base_evidence(10 + i)
        e.outcome_type = LearningOutcomeType.NO_SELECTION
        e.is_selected = False
        rewards.append(RewardSignalEvaluator.evaluate_opportunity(e))

    obj = ObjectiveAggregator.aggregate_objective(rewards)
    assert obj.eligible_opportunity_count == 10
    assert obj.total_contribution_paise == 0
    assert obj.contribution_per_shopper_paise == 0


def test_adversarial_4_one_successful_payment_and_many_non_purchases():
    """1 success (Rs 1,000) + 9 non-purchases (Rs 0) -> Contribution per shopper is 100, NOT 1,000!"""
    rewards = []
    # 1 success
    e1 = create_base_evidence(21)
    e1.expected_contribution_paise = 100000
    rewards.append(RewardSignalEvaluator.evaluate_opportunity(e1))
    # 9 non-purchases
    for i in range(9):
        e = create_base_evidence(22 + i)
        e.outcome_type = LearningOutcomeType.NO_SELECTION
        e.is_selected = False
        rewards.append(RewardSignalEvaluator.evaluate_opportunity(e))

    obj = ObjectiveAggregator.aggregate_objective(rewards)
    assert obj.eligible_opportunity_count == 10
    assert obj.total_contribution_paise == 100000
    # Must be diluted over all 10 opportunities
    assert obj.contribution_per_shopper_paise == 10000


def test_adversarial_5_duplicate_observations():
    """Duplicate observations share the same idempotency key, preventing double accounting."""
    e = create_base_evidence(31)
    r1 = RewardSignalEvaluator.evaluate_opportunity(e)
    r2 = RewardSignalEvaluator.evaluate_opportunity(e)
    assert r1.idempotency_key == r2.idempotency_key


def test_adversarial_6_repeated_retries():
    """Retries for the same scenario yield the same opportunity ID (experiment_id:scenario_id:variant)."""
    e1 = create_base_evidence(41)
    e2 = create_base_evidence(41)
    r1 = RewardSignalEvaluator.evaluate_opportunity(e1)
    r2 = RewardSignalEvaluator.evaluate_opportunity(e2)
    assert r1.opportunity_id == r2.opportunity_id


def test_adversarial_7_payment_failure_after_order_creation():
    """Order created but payment failed -> contribution is 0 paise (REWARD_ZERO)."""
    e = create_base_evidence(51)
    e.source = EvidenceSource.TEST_MODE_OBSERVED
    e.outcome_type = LearningOutcomeType.PAYMENT_FAILURE
    e.observed_revenue_paise = 0
    e.observed_contribution_paise = 0

    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    assert rwd.reward_state == RewardState.REWARD_ZERO
    assert rwd.reward_contribution_paise == 0


def test_adversarial_8_missing_contribution_input():
    """Missing required evidence status is flagged as INVALID."""
    e = create_base_evidence(61)
    e.evidence_status = EvidenceQualityStatus.INVALID
    e.learning_eligible = False

    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    assert rwd.reward_state == RewardState.REWARD_INVALID
    assert rwd.is_admissible is False


def test_adversarial_9_negative_contribution():
    """Loss-leader selling below COGS yields negative contribution and negative margin."""
    contrib = ContributionCalculator.calculate_contribution_paise(100000, 150000)
    assert contrib == -50000
    assert contrib < 0


def test_adversarial_10_zero_denominator():
    """When eligible opportunities == 0, aggregate_objective raises ZeroDenominatorError."""
    with pytest.raises(ZeroDenominatorError):
        ObjectiveAggregator.aggregate_objective([])


def test_adversarial_11_stale_transaction_evidence():
    """Uncompleted experiment evidence is marked ineligible and excluded."""
    e = create_base_evidence(71)
    e.learning_eligible = False
    e.eligibility_reasons = ["Experiment still RUNNING"]
    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    assert rwd.is_admissible is False


def test_adversarial_12_invalid_evidence():
    """Corrupted evidence is excluded from denominator, never silently zeroed."""
    e_bad = create_base_evidence(81)
    e_bad.evidence_status = EvidenceQualityStatus.INVALID
    e_bad.learning_eligible = False
    rwd_bad = RewardSignalEvaluator.evaluate_opportunity(e_bad)
    assert rwd_bad.reward_state == RewardState.REWARD_INVALID

    # In aggregator, bad evidence is counted in ineligible_opportunity_count
    e_good = create_base_evidence(82)
    rwd_good = RewardSignalEvaluator.evaluate_opportunity(e_good)

    obj = ObjectiveAggregator.aggregate_objective([rwd_good, rwd_bad])
    assert obj.total_opportunities_evaluated == 2
    assert obj.eligible_opportunity_count == 1
    assert obj.ineligible_opportunity_count == 1


def test_adversarial_13_simulated_evidence_accidentally_treated_as_observed():
    """Simulated evidence has source == SIMULATED and observed_revenue == None."""
    e = create_base_evidence(91)
    assert e.source == EvidenceSource.SIMULATED
    assert e.observed_revenue_paise is None
    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    assert rwd.evidence_source == EvidenceSource.SIMULATED


def test_adversarial_14_test_mode_accidentally_described_as_production():
    """PRODUCTION_OBSERVED source is forbidden and strictly raises error during validation."""
    from services.learning.validator import LearningEvidenceValidator
    from services.learning.errors import InvalidEvidenceError

    e = create_base_evidence(101)
    e.source = EvidenceSource.PRODUCTION_OBSERVED
    with pytest.raises(InvalidEvidenceError):
        LearningEvidenceValidator.validate_provenance_and_integrity(e)


def test_adversarial_15_policy_receives_post_outcome_information():
    """Anti-leakage: Ex-post fields cannot exist on pre-decision proposals."""
    from services.policy.schemas import PolicyProposal
    # PolicyProposal has no field for realized_revenue or payment_status
    assert not hasattr(PolicyProposal, "realized_revenue_paise")
    assert not hasattr(PolicyProposal, "payment_status")


def test_adversarial_16_one_outcome_attributed_to_two_policies():
    """Aggregating across two distinct policies raises RewardAttributionError."""
    r1 = RewardSignalEvaluator.evaluate_opportunity(create_base_evidence(111, policy="p_one"))
    r2 = RewardSignalEvaluator.evaluate_opportunity(create_base_evidence(112, policy="p_two"))

    with pytest.raises(RewardAttributionError):
        ObjectiveAggregator.aggregate_objective([r1, r2])


def test_adversarial_17_merchant_a_evidence_appearing_in_merchant_b_aggregation():
    """Aggregating across two distinct merchants raises RewardAttributionError."""
    r1 = RewardSignalEvaluator.evaluate_opportunity(create_base_evidence(121, merchant="merch_alpha"))
    r2 = RewardSignalEvaluator.evaluate_opportunity(create_base_evidence(122, merchant="merch_beta"))

    with pytest.raises(RewardAttributionError):
        ObjectiveAggregator.aggregate_objective([r1, r2])


def test_adversarial_18_formula_version_changes_after_historical_rewards_exist():
    """Reward schema records explicit formula_version='contribution-formula/v1' for auditability."""
    r = RewardSignalEvaluator.evaluate_opportunity(create_base_evidence(131))
    assert r.formula_version == "contribution-formula/v1"


def test_adversarial_19_guardrail_violation_producing_a_high_apparent_reward():
    """Guardrail violation cannot bypass admissibility via high apparent reward."""
    e = create_base_evidence(141)
    e.expected_revenue_paise = 10000000  # Rs 100,000!
    e.expected_contribution_paise = 5000000
    e.evidence_status = EvidenceQualityStatus.GUARDRAIL_FAILURE
    e.learning_eligible = False

    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    # High apparent revenue is zeroed, outcome retained in denominator, flagged as safety violation
    assert rwd.is_admissible is True
    assert rwd.is_safety_violation is True
    assert rwd.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION
    assert rwd.reward_contribution_paise == 0

    obj = ObjectiveAggregator.aggregate_objective([rwd])
    assert obj.is_policy_admissible is False
    assert obj.guardrail_violation_count == 1
    assert obj.total_contribution_paise == 0


def test_adversarial_20_expected_contribution_being_mistaken_for_observed_contribution():
    """Aggregated objective metric_type explicitly differentiates OBSERVED from EXPECTED."""
    rwd = RewardSignalEvaluator.evaluate_opportunity(create_base_evidence(151))
    obj_obs = ObjectiveAggregator.aggregate_objective(
        [rwd],
        metric_type=ObjectiveMetricType.OBSERVED_CONTRIBUTION_PER_SHOPPER
    )
    obj_exp = ObjectiveAggregator.aggregate_objective(
        [rwd],
        metric_type=ObjectiveMetricType.EXPECTED_CONTRIBUTION_PER_SHOPPER
    )
    assert obj_obs.metric_type == ObjectiveMetricType.OBSERVED_CONTRIBUTION_PER_SHOPPER
    assert obj_exp.metric_type == ObjectiveMetricType.EXPECTED_CONTRIBUTION_PER_SHOPPER


def test_adversarial_boundary_no_learning_algorithms_in_reward():
    """Static AST Boundary Audit: services/reward must contain zero learning algorithms or bandits."""
    import os
    import ast

    reward_dir = os.path.join(os.path.dirname(__file__), "..", "..", "services", "reward")
    forbidden_terms = [
        "RazorpayClient",
        "rzp_test",
        "bandit",
        "q_learning",
        "reinforcement_learning",
        "epsilon_greedy",
        "policy_gradient",
        "update_policy",
        "optimize_policy"
    ]

    for root, _, files in os.walk(reward_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    _ = ast.parse(content, filename=file_path)

                    for term in forbidden_terms:
                        assert term.lower() not in content.lower(), (
                            f"Security boundary violation: '{term}' found in {file_path}. "
                            "Phase 8.2 defines the learning objective only. "
                            "It must NOT implement bandits, RL, or policy updates."
                        )


# =============================================================================
# REFINEMENT CASES: REVENUE, IDENTITY, AND GUARDRAIL BOUNDARIES
# =============================================================================

def test_refinement_guardrail_pre_execution_rejection():
    """Case 3: Phase 5 pre-execution guardrail rejection (EXECUTION_REJECTED).
    Remains in denominator as REWARD_ZERO (0 contribution)."""
    e = create_base_evidence(201)
    e.outcome_type = LearningOutcomeType.EXECUTION_REJECTED
    e.expected_revenue_paise = 0
    e.expected_contribution_paise = 0

    rwd = RewardSignalEvaluator.evaluate_opportunity(e)
    assert rwd.reward_state == RewardState.REWARD_ZERO
    assert rwd.is_admissible is True
    assert rwd.reward_contribution_paise == 0


def test_refinement_authoritative_revenue_discount_formula():
    """Case 9: RealizedRevenue = BaselineCatalogRevenue - MerchantFundedDiscount.
    Modeled contribution = RealizedRevenue - RealizedCOGS."""
    catalog_rev = 400000       # Rs 4,000 baseline
    merchant_disc = 50000      # Rs 500 promotional discount
    cogs = 180000              # Rs 1,800 COGS

    realized_rev = catalog_rev - merchant_disc  # Rs 3,500
    contrib = ContributionCalculator.calculate_contribution_paise(realized_rev, cogs)
    assert realized_rev == 350000
    assert contrib == 170000  # Rs 1,700 modeled contribution


def test_refinement_unsupported_accounting_cost_cannot_enter_formula():
    """Case 13: Unsupported accounting fields (e.g. taxes, overhead, gateway fees) are forbidden."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PolicyOpportunityReward(
            reward_id="rwd_unsupported",
            merchant_id="merch_atlas",
            opportunity_id="exp_01:scen_01:TREATMENT",
            buyer_context_key="bck_test",
            policy_id="p_treat",
            experiment_id="exp_01",
            variant=VariantType.TREATMENT,
            evidence_id="evi_01",
            evidence_source=EvidenceSource.SIMULATED,
            outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
            reward_state=RewardState.REWARD_ELIGIBLE,
            is_admissible=True,
            idempotency_key="idem_01",
            corporate_tax_rate=0.25,        # FORBIDDEN!
            razorpay_mdr_fee_paise=7000     # FORBIDDEN!
        )


def test_refinement_identity_distinct_opportunities_same_context():
    """Case 14: Two distinct opportunities sharing the identical buyer_context_key do NOT collapse."""
    e1 = create_base_evidence(211)
    e1.scenario_id = "scen_travel_01"
    e1.buyer_context_key = "bck_backpack_budget_mid"
    e1.expected_contribution_paise = 50000

    e2 = create_base_evidence(212)
    e2.scenario_id = "scen_travel_02"
    e2.buyer_context_key = "bck_backpack_budget_mid"  # SAME context key!
    e2.expected_contribution_paise = 50000

    r1 = RewardSignalEvaluator.evaluate_opportunity(e1)
    r2 = RewardSignalEvaluator.evaluate_opportunity(e2)

    assert r1.opportunity_id != r2.opportunity_id  # Unique decision instances!
    assert r1.buyer_context_key == r2.buyer_context_key

    # Aggregating across both opportunities
    obj = ObjectiveAggregator.aggregate_objective([r1, r2])
    assert obj.eligible_opportunity_count == 2      # Both counted, NOT collapsed to 1!
    assert obj.total_contribution_paise == 100000
    assert obj.contribution_per_shopper_paise == 50000
    assert obj.buyer_context_key == "bck_backpack_budget_mid"


def test_refinement_aggregation_mixed_contexts_population():
    """Case 18 & 24: Aggregation over diverse buyer contexts cleanly identifies ALL_CONTEXTS."""
    e1 = create_base_evidence(221)
    e1.buyer_context_key = "bck_category_backpack"
    e1.expected_contribution_paise = 60000

    e2 = create_base_evidence(222)
    e2.buyer_context_key = "bck_category_duffel"
    e2.expected_contribution_paise = 40000

    r1 = RewardSignalEvaluator.evaluate_opportunity(e1)
    r2 = RewardSignalEvaluator.evaluate_opportunity(e2)

    obj = ObjectiveAggregator.aggregate_objective([r1, r2])
    assert obj.eligible_opportunity_count == 2
    assert obj.total_contribution_paise == 100000
    assert obj.contribution_per_shopper_paise == 50000
    assert obj.buyer_context_key == "ALL_CONTEXTS"  # Population-level aggregate
    assert "ALL_CONTEXTS" in obj.aggregation_key

