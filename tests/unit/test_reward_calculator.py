"""Unit tests for Phase 8.2 ContributionCalculator and RewardSignalEvaluator."""

from datetime import datetime, timezone
import pytest
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus
)
from services.reward.calculator import ContributionCalculator, RewardSignalEvaluator
from services.reward.schemas import RewardState


def test_contribution_calculator_exact_positive():
    """Exact integer paise contribution and exact Decimal margin calculation."""
    rev = 349900  # Rs 3,499.00
    cogs = 170000 # Rs 1,700.00
    contrib = ContributionCalculator.calculate_contribution_paise(rev, cogs)
    margin = ContributionCalculator.calculate_margin_percent(rev, cogs)

    assert contrib == 179900
    assert margin == 51.41


def test_contribution_calculator_negative_contribution_preserved():
    """Selling below COGS produces negative contribution; strictly NOT clamped to zero."""
    rev = 150000  # Rs 1,500.00
    cogs = 200000 # Rs 2,000.00
    contrib = ContributionCalculator.calculate_contribution_paise(rev, cogs)
    margin = ContributionCalculator.calculate_margin_percent(rev, cogs)

    assert contrib == -50000  # -Rs 500.00
    assert margin == -33.33   # Negative margin


def test_reward_signal_evaluator_payment_success():
    """Verified payment produces REWARD_ELIGIBLE with observed economic contribution."""
    evidence = PolicyLearningEvidence(
        evidence_id="evi_pay_succ",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas",
        experiment_id="exp_01",
        experiment_observation_id="obs_01",
        scenario_id="scen_01",
        policy_id="p_treat",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        sample_size=1,
        is_selected=True,
        observed_revenue_paise=350000,
        observed_contribution_paise=175000,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key="agg_01",
        idempotency_key="idem_pay_succ",
        observed_at=datetime.now(timezone.utc)
    )

    reward = RewardSignalEvaluator.evaluate_opportunity(evidence)
    assert reward.reward_state == RewardState.REWARD_ELIGIBLE
    assert reward.is_admissible is True
    assert reward.reward_contribution_paise == 175000
    assert reward.realized_revenue_paise == 350000


def test_reward_signal_evaluator_non_purchase_outcomes():
    """Non-purchase outcomes produce REWARD_ZERO (0 contribution, admissible in denominator)."""
    # 1. NO_SELECTION
    evidence_no_sel = PolicyLearningEvidence(
        evidence_id="evi_no_sel",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas",
        experiment_id="exp_01",
        experiment_observation_id="obs_02",
        scenario_id="scen_02",
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
        idempotency_key="idem_no_sel",
        observed_at=datetime.now(timezone.utc)
    )
    r_no_sel = RewardSignalEvaluator.evaluate_opportunity(evidence_no_sel)
    assert r_no_sel.reward_state == RewardState.REWARD_ZERO
    assert r_no_sel.is_admissible is True
    assert r_no_sel.reward_contribution_paise == 0

    # 2. ORDER_CREATED but unpaid
    evidence_unpaid = PolicyLearningEvidence(
        evidence_id="evi_unpaid",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas",
        experiment_id="exp_01",
        experiment_observation_id="obs_03",
        scenario_id="scen_03",
        policy_id="p_treat",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.ORDER_CREATED,
        sample_size=1,
        is_selected=True,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key="agg_01",
        idempotency_key="idem_unpaid",
        observed_at=datetime.now(timezone.utc)
    )
    r_unpaid = RewardSignalEvaluator.evaluate_opportunity(evidence_unpaid)
    assert r_unpaid.reward_state == RewardState.REWARD_ZERO
    assert r_unpaid.is_admissible is True
    assert r_unpaid.reward_contribution_paise == 0


def test_reward_signal_evaluator_ineligible_evidence_rejected():
    """Corrupt or insufficient sample evidence is classified as REWARD_INELIGIBLE and inadmissible."""
    evidence_inelig = PolicyLearningEvidence(
        evidence_id="evi_inelig",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas",
        experiment_id="exp_01",
        experiment_observation_id="obs_04",
        scenario_id="scen_04",
        policy_id="p_treat",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=300000,
        expected_contribution_paise=150000,
        evidence_status=EvidenceQualityStatus.INSUFFICIENT_SAMPLE,
        learning_eligible=False,
        eligibility_reasons=["Sample size too small"],
        aggregation_key="agg_01",
        idempotency_key="idem_inelig",
        observed_at=datetime.now(timezone.utc)
    )
    r_inelig = RewardSignalEvaluator.evaluate_opportunity(evidence_inelig)
    assert r_inelig.reward_state == RewardState.REWARD_INELIGIBLE
    assert r_inelig.is_admissible is False
    assert "insufficient_sample" in r_inelig.inadmissibility_reasons[0].lower()


def test_reward_signal_evaluator_guardrail_violation_retained():
    """Guardrail violations are classified as REWARD_GUARDRAIL_VIOLATION with 0 contribution and is_admissible=True."""
    evidence_guard = PolicyLearningEvidence(
        evidence_id="evi_guard",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas",
        experiment_id="exp_01",
        experiment_observation_id="obs_05",
        scenario_id="scen_05",
        policy_id="p_treat",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=300000,
        expected_contribution_paise=10000,
        margin_percent=3.33,
        evidence_status=EvidenceQualityStatus.GUARDRAIL_FAILURE,
        learning_eligible=False,
        eligibility_reasons=["Margin 3.33% below floor"],
        aggregation_key="agg_01",
        idempotency_key="idem_guard",
        observed_at=datetime.now(timezone.utc)
    )
    r_guard = RewardSignalEvaluator.evaluate_opportunity(evidence_guard)
    assert r_guard.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION
    assert r_guard.is_admissible is True
    assert r_guard.is_safety_violation is True
    assert r_guard.reward_contribution_paise == 0
