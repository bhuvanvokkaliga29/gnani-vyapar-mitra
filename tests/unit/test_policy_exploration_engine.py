"""Unit tests for Phase 8.7 & 8.7.1 Pure Deterministic Exploration Decision Engine.

Contract: policy-exploration/v1
Verifies:
- Hardened exploration triggers:
  * Uncertainty advantage trigger (with optimistic viability).
  * Under-observed policy trigger with Economic Eligibility rules (optimistic viability, bounded deficit, per-decision cap).
- Economic dominance prevention: under-observed candidate dominated by NO_OFFER or catastrophic deficit is rejected.
- Deterministic downside exposure formula:
  exposure = max(0, max(exploit_pred, baseline_pred) - explore_pred).
- Hard exposure guards: per-decision cap and cumulative window budget.
- Bounded risk controls (opportunity limit, consecutive limit, context cap, policy cap).
- Strict exclusion of exploit candidate and NO_OFFER baseline from exploration.
- Deterministic tie-breaking on UCB ranking.
"""

from datetime import datetime, timezone
import pytest

from services.policy.schemas import PolicyCandidate, StrategyType, CandidateValidationStatus
from services.selection.schemas import CandidateSelectionScore, PolicySelectionResult
from services.exploration.schemas import (
    MerchantExplorationConfig,
    ExplorationMode,
    ExplorationReasonCode
)
from services.exploration.engine import ExplorationEngine


@pytest.fixture
def base_candidates():
    c_exploit = PolicyCandidate(
        candidate_id="cand_exploit_01",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Top exploit candidate"
    )
    c_alt_high_unc = PolicyCandidate(
        candidate_id="cand_alt_unc_02",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_backpack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="High uncertainty alternative"
    )
    c_alt_under_obs = PolicyCandidate(
        candidate_id="cand_alt_obs_03",
        strategy_type=StrategyType.COMPLEMENTARY_BUNDLE,
        product_ids=["prod_backpack_01", "prod_sleeve_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Under-observed alternative"
    )
    c_baseline = PolicyCandidate(
        candidate_id="cand_base_no_offer",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Baseline reserve"
    )
    return {
        "cand_exploit_01": c_exploit,
        "cand_alt_unc_02": c_alt_high_unc,
        "cand_alt_obs_03": c_alt_under_obs,
        "cand_base_no_offer": c_baseline
    }


@pytest.fixture
def base_selection_result():
    scores = [
        CandidateSelectionScore(
            policy_id="cand_exploit_01",
            predicted_contribution_paise=50000,
            uncertainty=0.10,
            rank=1,
            is_baseline=False,
            selection_eligible=True
        ),
        CandidateSelectionScore(
            policy_id="cand_alt_unc_02",
            predicted_contribution_paise=45000,
            uncertainty=0.45,  # gap = 0.35 >= 0.20
            rank=2,
            is_baseline=False,
            selection_eligible=True
        ),
        CandidateSelectionScore(
            policy_id="cand_alt_obs_03",
            predicted_contribution_paise=40000,
            uncertainty=0.15,  # gap = 0.05 < 0.20
            rank=3,
            is_baseline=False,
            selection_eligible=True
        ),
        CandidateSelectionScore(
            policy_id="cand_base_no_offer",
            predicted_contribution_paise=0,
            uncertainty=0.0,
            rank=4,
            is_baseline=True,
            selection_eligible=True
        )
    ]
    return PolicySelectionResult(
        selection_id="sel_test_01",
        merchant_id="merch_unit_test",
        opportunity_id="opp_unit_01",
        buyer_context_key="bck_travel",
        selected_policy_id="cand_exploit_01",
        selected_policy_version="merchant-policy/v1",
        baseline_policy_id="cand_base_no_offer",
        selected_predicted_contribution_paise=50000,
        selected_uncertainty=0.10,
        baseline_predicted_contribution_paise=0,
        ranked_candidates=scores,
        selection_reason="Highest predicted contribution",
        selection_timestamp=datetime.now(timezone.utc)
    )


def test_exploit_when_exploration_disabled(base_candidates, base_selection_result):
    """When merchant config has enabled=False, engine must return EXPLOIT."""
    config = MerchantExplorationConfig(enabled=False)
    state = {}
    mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLOIT
    assert cand.candidate_id == "cand_exploit_01"
    assert exposure == 0
    assert reason == ExplorationReasonCode.EXPLOIT_DISABLED


def test_exploit_when_budget_exhausted(base_candidates, base_selection_result):
    """When opportunities_used >= max_exploration_opportunities, engine must return EXPLOIT."""
    config = MerchantExplorationConfig(max_exploration_opportunities=5)
    state = {"opportunities_used": 5}
    mode, cand, _, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLOIT
    assert cand.candidate_id == "cand_exploit_01"
    assert exposure == 0
    assert reason == ExplorationReasonCode.EXPLOIT_BUDGET_EXHAUSTED


def test_exploit_when_consecutive_limit_reached(base_candidates, base_selection_result):
    """When consecutive_explorations >= max_consecutive, engine must force EXPLOIT."""
    config = MerchantExplorationConfig(max_consecutive_explorations=2)
    state = {"consecutive_explorations": 2}
    mode, cand, _, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLOIT
    assert cand.candidate_id == "cand_exploit_01"
    assert exposure == 0
    assert reason == ExplorationReasonCode.EXPLOIT_CONSECUTIVE_LIMIT_REACHED


def test_exploit_when_exposure_limit_reached(base_candidates, base_selection_result):
    """When cumulative exposure >= max_exposure_paise, engine must return EXPLOIT."""
    config = MerchantExplorationConfig(max_exposure_paise=100000)
    state = {"exposure_paise_used": 100000}
    mode, cand, _, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLOIT
    assert cand.candidate_id == "cand_exploit_01"
    assert exposure == 0
    assert reason == ExplorationReasonCode.EXPLOIT_EXPOSURE_LIMIT_REACHED


def test_exploit_when_context_cap_reached(base_candidates, base_selection_result):
    """When buyer_context_key hits context exploration cap, engine must return EXPLOIT."""
    config = MerchantExplorationConfig(max_context_exploration_count=3)
    state = {"context_counts_json": {"bck_travel": 3}}
    mode, cand, _, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLOIT
    assert cand.candidate_id == "cand_exploit_01"
    assert exposure == 0
    assert reason == ExplorationReasonCode.EXPLOIT_CONTEXT_CAP_REACHED


def test_explore_when_uncertainty_advantage_triggered(base_candidates, base_selection_result):
    """When alternative has uncertainty gap >= 0.20 and optimistic viability, engine must EXPLORE."""
    config = MerchantExplorationConfig(min_uncertainty_gap=0.20)
    state = {"opportunities_used": 0, "consecutive_explorations": 0}
    # cand_alt_unc_02: pred=45,000, exploit=50,000. Gap = 5,000 paise.
    mode, cand, score, exposure, reason, diag = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLORE
    assert cand.candidate_id == "cand_alt_unc_02"
    assert exposure == 5000  # 50,000 - 45,000
    assert reason == ExplorationReasonCode.EXPLORE_UNCERTAINTY_ADVANTAGE
    assert diag["trigger_name"] == "UNCERTAINTY_ADVANTAGE"


def test_explore_when_under_observed_policy_triggered(base_candidates, base_selection_result):
    """When alternative has observation count < min_observations_threshold and is economically eligible, engine must EXPLORE."""
    config = MerchantExplorationConfig(min_uncertainty_gap=0.50, min_observations_threshold=5)
    state = {"opportunities_used": 0, "consecutive_explorations": 0}
    evidence = {
        "cand_exploit_01": 20,
        "cand_alt_unc_02": 10,  # >= 5
        "cand_alt_obs_03": 2    # < 5!
    }
    mode, cand, score, exposure, reason, diag = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state, evidence_counts=evidence
    )
    assert mode == ExplorationMode.EXPLORE
    assert cand.candidate_id == "cand_alt_obs_03"
    assert exposure == 10000  # 50,000 - 40,000
    assert reason == ExplorationReasonCode.EXPLORE_UNDER_OBSERVED_POLICY
    assert diag["trigger_name"] == "UNDER_OBSERVED_POLICY"


def test_under_observed_dominated_rejected(base_candidates, base_selection_result):
    """Phase 8.7.1: An under-observed candidate (N=0) with catastrophic negative prediction is rejected."""
    # Alter cand_alt_obs_03 to have catastrophic negative prediction (-₹500 / -50,000 paise)
    for s in base_selection_result.ranked_candidates:
        if s.policy_id == "cand_alt_obs_03":
            s.predicted_contribution_paise = -50000
            s.uncertainty = 0.10  # UCB = -50000 + 1000 = -49000 < 0 (worse than NO_OFFER baseline!)

    config = MerchantExplorationConfig(min_uncertainty_gap=0.50, min_observations_threshold=5)
    state = {"opportunities_used": 0, "consecutive_explorations": 0}
    evidence = {
        "cand_exploit_01": 20,
        "cand_alt_unc_02": 10,
        "cand_alt_obs_03": 0    # N = 0, but economically dominated!
    }
    mode, cand, _, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state, evidence_counts=evidence
    )
    # Must NOT explore the dominated candidate! Must safely EXPLOIT.
    assert mode == ExplorationMode.EXPLOIT
    assert cand.candidate_id == "cand_exploit_01"
    assert exposure == 0
    assert reason == ExplorationReasonCode.EXPLOIT_TRIGGER_NOT_SATISFIED


def test_per_decision_exposure_cap_disqualifies_candidate(base_candidates, base_selection_result):
    """Phase 8.7.1: Candidate whose downside exposure exceeds max_exposure_per_decision_paise is disqualified."""
    # Exploit = 50,000 paise. Cand_alt = 20,000 paise (downside = 30,000 paise).
    # If per-decision cap is 20,000 paise, it must be disqualified.
    config = MerchantExplorationConfig(
        max_exposure_per_decision_paise=20000,
        min_uncertainty_gap=0.20
    )
    state = {"opportunities_used": 0, "consecutive_explorations": 0}

    # cand_alt_unc_02 downside is 5,000 paise (passes cap 20,000)
    mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLORE
    assert cand.candidate_id == "cand_alt_unc_02"
    assert exposure == 5000

    # Now tighten per-decision cap to 4,000 paise (5,000 exceeds 4,000)
    config_tight = MerchantExplorationConfig(
        max_exposure_per_decision_paise=4000,
        min_uncertainty_gap=0.20
    )
    mode2, cand2, _, exposure2, reason2, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config_tight, state
    )
    assert mode2 == ExplorationMode.EXPLOIT
    assert cand2.candidate_id == "cand_exploit_01"
    assert exposure2 == 0


def test_exposure_formula_with_no_offer_floor(base_candidates, base_selection_result):
    """Phase 8.7.1: Downside exposure against NO_OFFER baseline when exploit is baseline."""
    # Set exploit candidate to NO_OFFER (0 paise)
    base_selection_result.selected_policy_id = "cand_base_no_offer"
    base_selection_result.selected_predicted_contribution_paise = 0
    base_selection_result.selected_uncertainty = 0.0

    # Only baseline and cand_alt_unc_02
    score_alt = None
    score_base = None
    for s in base_selection_result.ranked_candidates:
        if s.policy_id == "cand_alt_unc_02":
            s.predicted_contribution_paise = -5000
            s.uncertainty = 0.80  # UCB = -5000 + 8000 = +3000 >= 0
            score_alt = s
        elif s.policy_id == "cand_base_no_offer":
            score_base = s
    base_selection_result.ranked_candidates = [score_base, score_alt]

    config = MerchantExplorationConfig(min_uncertainty_gap=0.20)
    state = {}
    mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
        base_selection_result, base_candidates, config, state
    )
    assert mode == ExplorationMode.EXPLORE
    assert cand.candidate_id == "cand_alt_unc_02"
    # Downside against benchmark max(0, 0) - (-5000) = 5000 paise!
    assert exposure == 5000


def test_determinism_and_reproducibility(base_candidates, base_selection_result):
    """Identical state and inputs must produce identical exploration decisions and exposure."""
    config = MerchantExplorationConfig()
    state = {"opportunities_used": 1, "consecutive_explorations": 1}
    evidence = {"cand_alt_unc_02": 2}

    res1 = ExplorationEngine.evaluate_exploration(base_selection_result, base_candidates, config, state, evidence)
    res2 = ExplorationEngine.evaluate_exploration(base_selection_result, base_candidates, config, state, evidence)

    assert res1 == res2
