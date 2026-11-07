"""Unit Tests for Pure Deterministic Policy Promotion Evaluator (Phase 8.8 & Phase 8.8.1).

Contracts:
- policy-lifecycle/v1
- promotion-policy/v1
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from domain.models import PolicyMemoryRecord
from services.experiments.schemas import (
    ExperimentResult,
    ExperimentStatus,
    EvidenceStatus,
    VariantType,
    VariantMetrics,
    GuardrailResult,
    GuardrailType
)
from services.lifecycle.schemas import (
    PromotionPolicyConfig,
    PromotionFailureCode,
    PromotionEvidenceType
)
from services.lifecycle.evaluator import PolicyPromotionEvaluator


def _create_mock_memory_record(
    policy_id: str,
    contribution_paise: int,
    learning_eligible: bool = True,
    is_admissible: bool = True,
    is_safety_violation: bool = False,
    is_current: bool = True,
    policy_version: str = "merchant-policy/v1",
    opportunity_id: str = None,
    observed_at: datetime = None,
    buyer_context_key: str = "ctx_test"
) -> PolicyMemoryRecord:
    opp = opportunity_id or f"opp_{policy_id}_{uuid.uuid4().hex[:8]}"
    obs = observed_at or datetime.now(timezone.utc)
    rec = PolicyMemoryRecord(
        id=f"mem_{policy_id}_{uuid.uuid4().hex[:6]}",
        merchant_id="merch_unit_test",
        opportunity_id=opp,
        buyer_context_key=buyer_context_key,
        scenario_id="scen_test",
        policy_id=policy_id,
        policy_version=policy_version,
        experiment_id="exp_test",
        experiment_version="policy-experiment/v1",
        variant="TREATMENT",
        evidence_id="evi_test",
        evidence_source="SIMULATED",
        outcome_type="TEST_MODE_COMPLETED",
        learning_eligible=learning_eligible,
        reward_id="rew_test",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state="FINAL",
        is_admissible=is_admissible,
        is_safety_violation=is_safety_violation,
        is_current=is_current,
        reward_contribution_paise=contribution_paise,
        observed_at=obs
    )
    return rec


def test_eligible_candidate_passes_all_criteria():
    """Candidate with sufficient sample, positive contribution, outperforming baseline, and 0 violations passes."""
    cand_records = [_create_mock_memory_record("cand_good", 50000) for _ in range(25)]
    base_records = [_create_mock_memory_record("cand_base", 30000) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20, min_positive_contribution_paise=1)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_good",
        config=config,
        memory_records=cand_records,
        baseline_records=base_records
    )

    assert is_eligible is True
    assert failure_codes == []
    assert summary["sample_size"] == 25
    assert summary["mean_observed_contribution_paise"] == 50000.0
    assert summary["improvement_over_baseline_paise"] == 20000.0
    assert summary["evidence_type"] == PromotionEvidenceType.OBSERVATIONAL_HISTORY.value
    assert summary["observational_bias_warning"] is not None


def test_insufficient_sample_size_rejected():
    """Candidate with fewer than minimum required observations is rejected."""
    cand_records = [_create_mock_memory_record("cand_small", 50000) for _ in range(12)]
    base_records = [_create_mock_memory_record("cand_base", 30000) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_small",
        config=config,
        memory_records=cand_records,
        baseline_records=base_records
    )

    assert is_eligible is False
    assert PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes
    assert summary["sample_size"] == 12


def test_historical_safety_violations_rejected():
    """Candidate with historical safety violations in memory is rejected."""
    records = [_create_mock_memory_record("cand_unsafe", 60000) for _ in range(23)]
    records.append(_create_mock_memory_record("cand_unsafe", 60000, is_safety_violation=True))
    records.append(_create_mock_memory_record("cand_unsafe", 60000, is_safety_violation=True))

    config = PromotionPolicyConfig(min_learning_opportunities=20, max_tolerated_safety_violations=0)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_unsafe",
        config=config,
        memory_records=records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.GUARDRAIL_BREACH in failure_codes
    assert summary["safety_violations_count"] == 2


def test_negative_observed_contribution_rejected():
    """Candidate with negative observed contribution is rejected."""
    cand_records = [_create_mock_memory_record("cand_neg", -15000) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20, min_positive_contribution_paise=1)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_neg",
        config=config,
        memory_records=cand_records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.NEGATIVE_CONTRIBUTION in failure_codes
    assert summary["mean_observed_contribution_paise"] == -15000.0


def test_underperforming_baseline_rejected():
    """Candidate underperforming the baseline is rejected."""
    cand_records = [_create_mock_memory_record("cand_low", 25000) for _ in range(25)]
    base_records = [_create_mock_memory_record("cand_base", 40000) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20, min_improvement_over_baseline_paise=0)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_low",
        config=config,
        memory_records=cand_records,
        baseline_records=base_records
    )

    assert is_eligible is False
    assert PromotionFailureCode.NO_IMPROVEMENT_OVER_BASELINE in failure_codes
    assert summary["improvement_over_baseline_paise"] == -15000.0


def test_controlled_experiment_required_and_missing():
    """When controlled experiment is required, missing experiment result causes rejection."""
    cand_records = [_create_mock_memory_record("cand_exp", 50000) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20, require_controlled_experiment=True)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_exp",
        config=config,
        memory_records=cand_records,
        baseline_records=[],
        experiment_result=None
    )

    assert is_eligible is False
    assert PromotionFailureCode.EXPERIMENT_NOT_FOUND in failure_codes


def test_controlled_experiment_inconclusive_rejected():
    """When experiment evidence status is INCONCLUSIVE, promotion is rejected."""
    cand_records = [_create_mock_memory_record("cand_exp", 50000) for _ in range(25)]

    exp_res = ExperimentResult(
        experiment_id="exp_inconcl",
        merchant_id="merch_unit_test",
        status=ExperimentStatus.COMPLETED,
        evidence_status=EvidenceStatus.INCONCLUSIVE,
        winner=None,
        winner_rationale="Insufficient statistical power",
        sample_counts={"CONTROL": 10, "TREATMENT": 10},
        control_metrics=VariantMetrics(sample_size=10, total_contribution_paise=20000, expected_contribution_per_shopper_paise=2000),
        treatment_metrics=VariantMetrics(sample_size=10, total_contribution_paise=20000, expected_contribution_per_shopper_paise=2000),
        metric_deltas={},
        guardrail_results=[]
    )

    config = PromotionPolicyConfig(min_learning_opportunities=20, require_controlled_experiment=True)
    is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_exp",
        config=config,
        memory_records=cand_records,
        baseline_records=[],
        experiment_result=exp_res
    )

    assert is_eligible is False
    assert PromotionFailureCode.INCONCLUSIVE_EXPERIMENT in failure_codes


def test_controlled_experiment_guardrail_failure_rejected():
    """When experiment has a failing guardrail, promotion is rejected."""
    cand_records = [_create_mock_memory_record("cand_exp", 50000) for _ in range(25)]

    exp_res = ExperimentResult(
        experiment_id="exp_gr_fail",
        merchant_id="merch_unit_test",
        status=ExperimentStatus.COMPLETED,
        evidence_status=EvidenceStatus.GUARDRAIL_FAILURE,
        winner=VariantType.TREATMENT,
        winner_rationale="Higher contribution but breached margin",
        sample_counts={"CONTROL": 20, "TREATMENT": 20},
        control_metrics=VariantMetrics(sample_size=20, total_contribution_paise=50000, expected_contribution_per_shopper_paise=2500),
        treatment_metrics=VariantMetrics(sample_size=20, total_contribution_paise=80000, expected_contribution_per_shopper_paise=4000),
        metric_deltas={},
        guardrail_results=[
            GuardrailResult(
                guardrail_type=GuardrailType.MIN_MARGIN_PERCENT,
                threshold_value=15.0,
                observed_value=12.0,
                passed=False,
                detail="Margin 12% below 15% floor"
            )
        ]
    )

    config = PromotionPolicyConfig(min_learning_opportunities=20)
    is_eligible, failure_codes, _ = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_exp",
        config=config,
        memory_records=cand_records,
        baseline_records=[],
        experiment_result=exp_res
    )

    assert is_eligible is False
    assert PromotionFailureCode.GUARDRAIL_BREACH in failure_codes


def test_controlled_experiment_successful_promotion():
    """Controlled experiment with sufficient evidence, treatment win, and passing guardrails is promoted with CONTROLLED_EXPERIMENT evidence type."""
    cand_records = [_create_mock_memory_record("cand_exp_win", 60000) for _ in range(25)]
    base_records = [_create_mock_memory_record("cand_base", 30000) for _ in range(25)]

    exp_res = ExperimentResult(
        experiment_id="exp_win_1",
        merchant_id="merch_unit_test",
        status=ExperimentStatus.COMPLETED,
        evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE,
        winner=VariantType.TREATMENT,
        winner_rationale="Statistically significant improvement",
        sample_counts={"CONTROL": 25, "TREATMENT": 25},
        control_metrics=VariantMetrics(sample_size=25, total_contribution_paise=750000, expected_contribution_per_shopper_paise=30000),
        treatment_metrics=VariantMetrics(sample_size=25, total_contribution_paise=1500000, expected_contribution_per_shopper_paise=60000),
        metric_deltas={},
        guardrail_results=[
            GuardrailResult(
                guardrail_type=GuardrailType.MIN_MARGIN_PERCENT,
                threshold_value=15.0,
                observed_value=22.0,
                passed=True,
                detail="Margin 22% satisfies 15% floor"
            )
        ]
    )

    config = PromotionPolicyConfig(min_learning_opportunities=20, require_controlled_experiment=True)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_exp_win",
        config=config,
        memory_records=cand_records,
        baseline_records=base_records,
        experiment_result=exp_res
    )

    assert is_eligible is True
    assert failure_codes == []
    assert summary["evidence_type"] == PromotionEvidenceType.CONTROLLED_EXPERIMENT.value
    assert summary["observational_bias_warning"] is None


def test_stale_evidence_rejected():
    """Observations older than the recency window are rejected as STALE_EVIDENCE."""
    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
    # Observations from 60 days ago (recency window is 30 days)
    old_time = now - timedelta(days=60)
    cand_records = [_create_mock_memory_record("cand_old", 50000, observed_at=old_time) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20, recency_window_days=30)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_old",
        config=config,
        memory_records=cand_records,
        baseline_records=[],
        evaluation_time=now
    )

    assert is_eligible is False
    assert PromotionFailureCode.STALE_EVIDENCE in failure_codes
    assert summary["stale_records_count"] == 25
    assert summary["sample_size"] == 0


def test_future_evidence_rejected():
    """Observations timestamped in the future are rejected."""
    now = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
    future_time = now + timedelta(days=5)
    cand_records = [_create_mock_memory_record("cand_fut", 50000, observed_at=future_time) for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_fut",
        config=config,
        memory_records=cand_records,
        baseline_records=[],
        evaluation_time=now
    )

    assert is_eligible is False
    assert PromotionFailureCode.FUTURE_EVIDENCE_REJECTED in failure_codes
    assert summary["future_records_count"] == 25


def test_superseded_records_excluded():
    """Superseded observations (is_current=False) do not contribute to sample size."""
    # 15 current records, 10 superseded records
    cand_records = [_create_mock_memory_record("cand_sup", 50000, is_current=True) for _ in range(15)]
    cand_records.extend([_create_mock_memory_record("cand_sup", 50000, is_current=False) for _ in range(10)])

    config = PromotionPolicyConfig(min_learning_opportunities=20)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_sup",
        config=config,
        memory_records=cand_records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes
    assert summary["sample_size"] == 15
    assert summary["superseded_records_count"] == 10


def test_duplicate_opportunity_deduplication():
    """Multiple records with identical opportunity_id count as only one observation."""
    # Create 25 records but all with the same 5 opportunity IDs (5 each)
    cand_records = []
    for opp_idx in range(5):
        for _ in range(5):
            cand_records.append(_create_mock_memory_record("cand_dup", 50000, opportunity_id=f"opp_shared_{opp_idx}"))

    config = PromotionPolicyConfig(min_learning_opportunities=20)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_dup",
        config=config,
        memory_records=cand_records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes
    # Deduplicated from 25 records down to 5 distinct opportunities
    assert summary["sample_size"] == 5


def test_policy_version_mismatch_rejected():
    """Evidence for candidate under policy_version v1 cannot satisfy promotion for version v2."""
    # 25 records under merchant-policy/v1
    cand_records = [_create_mock_memory_record("cand_ver", 50000, policy_version="merchant-policy/v1") for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20)
    # Attempting to promote under version merchant-policy/v2
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_ver",
        config=config,
        memory_records=cand_records,
        baseline_records=[],
        candidate_policy_version="merchant-policy/v2"
    )

    assert is_eligible is False
    assert PromotionFailureCode.POLICY_VERSION_MISMATCH in failure_codes
    assert summary["sample_size"] == 0
    assert summary["version_matching_records_count"] == 0
    assert summary["raw_candidate_records_count"] == 25


def test_observational_concentration_limit_breach():
    """Single opportunity accounting for > 50% of total contribution breaches concentration limit."""
    # 24 records with 1,000 paise and 1 record with 100,000 paise
    # Total = 124,000 paise. 100,000 / 124,000 = 80.6% > 50%
    cand_records = [_create_mock_memory_record("cand_dom", 1000) for _ in range(24)]
    cand_records.append(_create_mock_memory_record("cand_dom", 100000))

    config = PromotionPolicyConfig(min_learning_opportunities=20, max_opportunity_contribution_share=0.50)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_dom",
        config=config,
        memory_records=cand_records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.OBSERVATIONAL_CONCENTRATION_EXCEEDED in failure_codes
    assert summary["concentration"]["max_single_opp_share"] > 0.50


def test_insufficient_context_diversity():
    """When minimum distinct buyer contexts are required, failing diversity is rejected."""
    # 25 records all in the single context 'ctx_mono'
    cand_records = [_create_mock_memory_record("cand_mono", 50000, buyer_context_key="ctx_mono") for _ in range(25)]

    config = PromotionPolicyConfig(min_learning_opportunities=20, min_distinct_contexts=3)
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_mono",
        config=config,
        memory_records=cand_records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.INSUFFICIENT_CONTEXT_DIVERSITY in failure_codes
    assert summary["context_coverage"]["distinct_contexts_count"] == 1


def test_higher_observational_sample_requirement():
    """When min_observational_learning_opportunities is configured higher (e.g. 30), 25 records fail."""
    cand_records = [_create_mock_memory_record("cand_obs_strict", 50000) for _ in range(25)]

    config = PromotionPolicyConfig(
        min_learning_opportunities=20,
        min_observational_learning_opportunities=30
    )
    is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
        candidate_policy_id="cand_obs_strict",
        config=config,
        memory_records=cand_records,
        baseline_records=[]
    )

    assert is_eligible is False
    assert PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE in failure_codes
    assert summary["min_required_sample"] == 30
    assert summary["sample_size"] == 25


def test_determinism_and_reproducibility():
    """Identical evidence and configuration produce identical outcomes."""
    fixed_time = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
    cand_records = [_create_mock_memory_record("cand_det", 45000, opportunity_id=f"opp_det_{i}", observed_at=fixed_time) for i in range(25)]
    base_records = [_create_mock_memory_record("cand_base", 35000, opportunity_id=f"opp_base_{i}", observed_at=fixed_time) for i in range(25)]
    config = PromotionPolicyConfig(min_learning_opportunities=20)

    res1 = PolicyPromotionEvaluator.evaluate_promotion_eligibility("cand_det", config, cand_records, base_records, evaluation_time=fixed_time)
    res2 = PolicyPromotionEvaluator.evaluate_promotion_eligibility("cand_det", config, cand_records, base_records, evaluation_time=fixed_time)

    assert res1 == res2
