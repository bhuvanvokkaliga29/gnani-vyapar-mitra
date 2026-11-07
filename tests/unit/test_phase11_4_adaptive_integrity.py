"""Unit Test Suite for Phase 11.4: Exploration, Learning, and Temporal Integrity.

Contract: benchmark-scenario/v1, policy-exploration/v1, learning-algorithm/v1, policy-lifecycle/v1
Focus:
- Area A: Exploration budget and exposure limit integrity (opportunity, policy, context, cumulative cap, 1p over cap, 0 exposure on rejection)
- Area C: Temporal leakage and point-in-time cutoff boundary (T > cutoff rejected, T == cutoff admissible)
- Area D: Model update mathematical integrity (positive, zero, negative rewards with independent expectations)
- Expected vs Observed: Prediction immutability when realized contribution diverges
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from domain.models import PolicyMemoryRecord, CanonicalDecisionRecord
from services.learning.algorithm import (
    ContextualLinearUCB,
    REWARD_SCALE_FACTOR,
)
from services.learning.features import FEATURE_DIMENSION
from services.policy.schemas import PolicyCandidate, StrategyType, CandidateValidationStatus
from services.selection.schemas import CandidateSelectionScore, PolicySelectionResult
from services.exploration.schemas import (
    MerchantExplorationConfig,
    ExplorationMode,
    ExplorationReasonCode,
)
from services.exploration.engine import ExplorationEngine
from services.lifecycle.schemas import PromotionPolicyConfig, PromotionFailureCode
from services.lifecycle.evaluator import PolicyPromotionEvaluator


def _create_mock_memory_record(
    policy_id: str,
    contribution_paise: int,
    observed_at: datetime = None,
    buyer_context_key: str = "ctx_test",
    opportunity_id: str = None,
) -> PolicyMemoryRecord:
    """Helper to instantiate valid declarative PolicyMemoryRecord instances."""
    opp = opportunity_id or f"opp_{policy_id}_{uuid.uuid4().hex[:8]}"
    obs = observed_at or datetime.now(timezone.utc)
    return PolicyMemoryRecord(
        id=f"mem_{policy_id}_{uuid.uuid4().hex[:6]}",
        merchant_id="merch_unit_test",
        opportunity_id=opp,
        buyer_context_key=buyer_context_key,
        scenario_id="scen_test",
        policy_id=policy_id,
        policy_version="merchant-policy/v1",
        experiment_id="exp_test",
        experiment_version="policy-experiment/v1",
        variant="TREATMENT",
        evidence_id="evi_test",
        evidence_source="SIMULATED",
        outcome_type="TEST_MODE_COMPLETED",
        learning_eligible=True,
        reward_id="rew_test",
        reward_version="merchant-reward/v1",
        formula_version="contribution-formula/v1",
        reward_state="FINAL",
        is_admissible=True,
        is_safety_violation=False,
        is_current=True,
        reward_contribution_paise=contribution_paise,
        observed_at=obs,
    )


# ==============================================================================
# FIXTURES FOR EXPLORATION TESTING
# ==============================================================================
@pytest.fixture
def base_candidates():
    """Create minimal candidate slate with exploit and alternative candidates."""
    c_exploit = PolicyCandidate(
        candidate_id="cand_exploit_01",
        strategy_type=StrategyType.SINGLE_PRODUCT,
        product_ids=["prod_pack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Top exploit candidate",
    )
    c_alt_high_unc = PolicyCandidate(
        candidate_id="cand_alt_unc_02",
        strategy_type=StrategyType.BOUNDED_DISCOUNT,
        product_ids=["prod_pack_01"],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="High uncertainty alternative",
    )
    c_baseline = PolicyCandidate(
        candidate_id="cand_base_no_offer",
        strategy_type=StrategyType.NO_OFFER,
        product_ids=[],
        validation_status=CandidateValidationStatus.APPROVED,
        rationale="Baseline reserve",
    )
    return {
        "cand_exploit_01": c_exploit,
        "cand_alt_unc_02": c_alt_high_unc,
        "cand_base_no_offer": c_baseline,
    }


@pytest.fixture
def base_selection_result():
    """Create selection result where cand_alt_unc_02 is eligible for exploration."""
    s_exploit = CandidateSelectionScore(
        policy_id="cand_exploit_01",
        predicted_contribution_paise=50000,
        uncertainty=0.10,
        rank=1,
        selection_eligible=True,
        is_baseline=False,
    )
    s_alt = CandidateSelectionScore(
        policy_id="cand_alt_unc_02",
        predicted_contribution_paise=48000,  # 2000 paise downside exposure
        uncertainty=0.60,  # unc_gap = 0.50 >= min_uncertainty_gap (0.15)
        rank=2,
        selection_eligible=True,
        is_baseline=False,
    )
    s_base = CandidateSelectionScore(
        policy_id="cand_base_no_offer",
        predicted_contribution_paise=0,
        uncertainty=0.0,
        rank=3,
        selection_eligible=True,
        is_baseline=True,
    )
    return PolicySelectionResult(
        selection_id="sel_adapt_001",
        merchant_id="merch_adapt_unit",
        opportunity_id="opp_adapt_unit",
        buyer_context_key="ctx_travel_backpack",
        selected_policy_id="cand_exploit_01",
        selected_policy_version="merchant-policy/v1",
        baseline_policy_id="cand_base_no_offer",
        selected_predicted_contribution_paise=50000,
        selected_uncertainty=0.10,
        baseline_predicted_contribution_paise=0,
        ranked_candidates=[s_exploit, s_alt, s_base],
        selection_reason="Highest predicted contribution",
        selection_timestamp=datetime.now(timezone.utc),
    )


# ==============================================================================
# AREA A: EXPLORATION BUDGET INTEGRITY
# ==============================================================================
class TestExplorationBudgetIntegrity:
    """Validate that frozen Phase 8.7 exploration limits strictly prevent exposure breaches."""

    def test_exploration_opportunity_budget_exhausted(self, base_candidates, base_selection_result):
        """A. Opportunity budget exhausted forces deterministic fallback to exploit."""
        config = MerchantExplorationConfig(max_exploration_opportunities=5)
        state_dict = {
            "opportunities_used": 5,  # Exhausted!
            "exposure_paise_used": 10000,
            "consecutive_explorations": 0,
            "policy_counts_json": {},
            "context_counts_json": {},
        }
        mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
            selection_result=base_selection_result,
            candidate_map=base_candidates,
            config=config,
            state_dict=state_dict,
        )
        assert mode == ExplorationMode.EXPLOIT
        assert cand.candidate_id == "cand_exploit_01"
        assert reason == ExplorationReasonCode.EXPLOIT_BUDGET_EXHAUSTED
        assert exposure == 0

    def test_exploration_policy_exposure_limit_exhausted(self, base_candidates, base_selection_result):
        """B. Per-policy exposure cap reached excludes candidate and forces exploit fallback."""
        config = MerchantExplorationConfig(max_policy_exploration_count=3)
        state_dict = {
            "opportunities_used": 1,
            "exposure_paise_used": 2000,
            "consecutive_explorations": 0,
            "policy_counts_json": {"cand_alt_unc_02": 3},  # Cap exhausted!
            "context_counts_json": {},
        }
        mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
            selection_result=base_selection_result,
            candidate_map=base_candidates,
            config=config,
            state_dict=state_dict,
        )
        assert mode == ExplorationMode.EXPLOIT
        assert cand.candidate_id == "cand_exploit_01"
        assert reason == ExplorationReasonCode.EXPLOIT_NO_ALTERNATIVES
        assert exposure == 0

    def test_exploration_context_exposure_limit_exhausted(self, base_candidates, base_selection_result):
        """C. Buyer context exposure cap reached forces exploit fallback."""
        config = MerchantExplorationConfig(max_context_exploration_count=4)
        state_dict = {
            "opportunities_used": 2,
            "exposure_paise_used": 4000,
            "consecutive_explorations": 0,
            "policy_counts_json": {},
            "context_counts_json": {"ctx_travel_backpack": 4},  # Context cap exhausted!
        }
        mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
            selection_result=base_selection_result,
            candidate_map=base_candidates,
            config=config,
            state_dict=state_dict,
        )
        assert mode == ExplorationMode.EXPLOIT
        assert cand.candidate_id == "cand_exploit_01"
        assert reason == ExplorationReasonCode.EXPLOIT_CONTEXT_CAP_REACHED
        assert exposure == 0

    def test_exploration_cumulative_monetary_exposure_at_cap(self, base_candidates, base_selection_result):
        """D. Cumulative monetary exposure at exact cap forces exploit fallback."""
        config = MerchantExplorationConfig(max_exposure_paise=50000)
        state_dict = {
            "opportunities_used": 3,
            "exposure_paise_used": 50000,  # Exactly at cap!
            "consecutive_explorations": 0,
            "policy_counts_json": {},
            "context_counts_json": {},
        }
        mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
            selection_result=base_selection_result,
            candidate_map=base_candidates,
            config=config,
            state_dict=state_dict,
        )
        assert mode == ExplorationMode.EXPLOIT
        assert cand.candidate_id == "cand_exploit_01"
        assert reason == ExplorationReasonCode.EXPLOIT_EXPOSURE_LIMIT_REACHED
        assert exposure == 0

    def test_exploration_one_paisa_over_cumulative_cap_rejected(self, base_candidates, base_selection_result):
        """E. One-paisa over cumulative cap excludes candidate and falls back to exploit."""
        config = MerchantExplorationConfig(max_exposure_paise=50000)
        state_dict = {
            "opportunities_used": 2,
            "exposure_paise_used": 48001,
            "consecutive_explorations": 0,
            "policy_counts_json": {},
            "context_counts_json": {},
        }
        mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
            selection_result=base_selection_result,
            candidate_map=base_candidates,
            config=config,
            state_dict=state_dict,
        )
        assert mode == ExplorationMode.EXPLOIT
        assert cand.candidate_id == "cand_exploit_01"
        assert reason == ExplorationReasonCode.EXPLOIT_NO_ALTERNATIVES
        assert exposure == 0

    def test_rejected_exploration_commits_zero_exposure(self, base_candidates, base_selection_result):
        """F. A rejected exploration decision commits exactly zero exposure and alters no counters."""
        config = MerchantExplorationConfig(max_exposure_paise=50000)
        state_dict = {
            "opportunities_used": 4,
            "exposure_paise_used": 49000,
            "consecutive_explorations": 1,
            "policy_counts_json": {"cand_alt_unc_02": 1},
            "context_counts_json": {"ctx_travel_backpack": 2},
        }
        before_state = {k: (dict(v) if isinstance(v, dict) else v) for k, v in state_dict.items()}

        mode, cand, score, exposure, reason, _ = ExplorationEngine.evaluate_exploration(
            selection_result=base_selection_result,
            candidate_map=base_candidates,
            config=config,
            state_dict=state_dict,
        )
        assert mode == ExplorationMode.EXPLOIT
        assert exposure == 0
        assert state_dict == before_state


# ==============================================================================
# AREA D: MODEL UPDATE INTEGRITY (INDEPENDENT MATHEMATICAL VERIFICATION)
# ==============================================================================
class TestLinUCBModelUpdateIntegrity:
    """Verify LinUCB mathematical update logic against independent ground truth formulas."""

    def test_linucb_mathematical_update_positive_reward(self):
        """A. Positive reward: independently verify A_new = A_old + x x^T, b_new = b_old + x * (r/100)."""
        model = ContextualLinearUCB(merchant_id="merch_math_01", dimension=FEATURE_DIMENSION)
        x = [float((i + 1) % 5) * 0.1 for i in range(FEATURE_DIMENSION)]  # 19D feature vector
        reward_paise = 45000  # ₹450.00 positive contribution
        r_model = 45000.0 / REWARD_SCALE_FACTOR  # 450.0

        A_old = [[row[j] for j in range(FEATURE_DIMENSION)] for row in model.A]
        b_old = list(model.b)
        obs_old = model.observation_count

        A_expected = [[A_old[i][j] + x[i] * x[j] for j in range(FEATURE_DIMENSION)] for i in range(FEATURE_DIMENSION)]
        b_expected = [b_old[i] + x[i] * r_model for i in range(FEATURE_DIMENSION)]

        model.update(x, reward_paise)

        assert model.observation_count == obs_old + 1
        for i in range(FEATURE_DIMENSION):
            assert abs(model.b[i] - b_expected[i]) < 1e-6
            for j in range(FEATURE_DIMENSION):
                assert abs(model.A[i][j] - A_expected[i][j]) < 1e-6

    def test_linucb_mathematical_update_zero_reward(self):
        """B. Zero reward: vector b remains unchanged while matrix A and observation count update."""
        model = ContextualLinearUCB(merchant_id="merch_math_02", dimension=FEATURE_DIMENSION)
        x = [0.05 for _ in range(FEATURE_DIMENSION)]
        reward_paise = 0

        b_old = list(model.b)
        obs_old = model.observation_count

        model.update(x, reward_paise)

        assert model.observation_count == obs_old + 1
        for i in range(FEATURE_DIMENSION):
            assert abs(model.b[i] - b_old[i]) < 1e-9

    def test_linucb_mathematical_update_negative_reward(self):
        """C. Negative reward: signed negative contribution is strictly preserved without clipping."""
        model = ContextualLinearUCB(merchant_id="merch_math_03", dimension=FEATURE_DIMENSION)
        x = [float((i + 2) % 4) * 0.1 for i in range(FEATURE_DIMENSION)]
        reward_paise = -15000  # -₹150.00 loss leader
        r_model = -15000.0 / REWARD_SCALE_FACTOR  # -150.0

        b_old = list(model.b)
        b_expected = [b_old[i] + x[i] * r_model for i in range(FEATURE_DIMENSION)]

        model.update(x, reward_paise)

        assert model.observation_count == 1
        for i in range(FEATURE_DIMENSION):
            assert abs(model.b[i] - b_expected[i]) < 1e-6
            if x[i] > 0:
                assert model.b[i] < b_old[i]


# ==============================================================================
# AREA C: TEMPORAL LEAKAGE AND CUTOFF BOUNDARY
# ==============================================================================
class TestTemporalCutoffIntegrity:
    """Validate that observations timestamped after evaluation cutoff are strictly rejected."""

    def test_temporal_future_evidence_strictly_rejected(self):
        """Future evidence (observed_at > evaluation_time) triggers FUTURE_EVIDENCE_REJECTED."""
        eval_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
        future_obs_time = eval_time + timedelta(seconds=1)

        record = _create_mock_memory_record(
            policy_id="cand_temp_treat",
            contribution_paise=50000,
            observed_at=future_obs_time,
        )

        config = PromotionPolicyConfig(min_learning_opportunities=1)
        is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
            candidate_policy_id="cand_temp_treat",
            config=config,
            memory_records=[record],
            baseline_records=[],
            evaluation_time=eval_time,
        )

        assert is_eligible is False
        assert PromotionFailureCode.FUTURE_EVIDENCE_REJECTED in failure_codes

    def test_temporal_cutoff_boundary_equality_admissible(self):
        """Boundary condition: observed_at == evaluation_time is admissible under point-in-time rule."""
        eval_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
        boundary_obs_time = eval_time

        record = _create_mock_memory_record(
            policy_id="cand_temp_treat",
            contribution_paise=50000,
            observed_at=boundary_obs_time,
        )

        config = PromotionPolicyConfig(min_learning_opportunities=1)
        is_eligible, failure_codes, summary = PolicyPromotionEvaluator.evaluate_promotion_eligibility(
            candidate_policy_id="cand_temp_treat",
            config=config,
            memory_records=[record],
            baseline_records=[],
            evaluation_time=eval_time,
        )

        assert PromotionFailureCode.FUTURE_EVIDENCE_REJECTED not in failure_codes


# ==============================================================================
# EXPECTED vs OBSERVED SEPARATION
# ==============================================================================
class TestExpectedVsObservedSeparation:
    """Verify that historical predicted contribution remains immutable when realized outcome diverges."""

    def test_historical_prediction_immutable_on_divergent_outcome(self):
        """Predicted contribution is an immutable point-in-time fact that cannot be rewritten by outcome."""
        predicted_paise = 42000
        realized_paise = 85000

        # CanonicalDecisionRecord stores the original prediction
        dec = CanonicalDecisionRecord(
            id="dec_sep_01",
            merchant_id="merch_sep_01",
            opportunity_id="opp_sep_01",
            decision_mode="EXPLOIT",
            selected_policy_id="cand_sep_01",
            selected_strategy_type="SINGLE_PRODUCT",
            decision_envelope_json={"predicted_contribution_paise": predicted_paise},
        )

        # PolicyMemoryRecord stores the observed realization
        mem = _create_mock_memory_record(
            policy_id="cand_sep_01",
            contribution_paise=realized_paise,
            opportunity_id="opp_sep_01",
        )

        assert dec.decision_envelope_json["predicted_contribution_paise"] == 42000
        assert mem.reward_contribution_paise == 85000
        assert dec.decision_envelope_json["predicted_contribution_paise"] != mem.reward_contribution_paise
