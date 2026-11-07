"""Pure Deterministic Decision Engine for Policy Exploration vs Exploitation.

Contract: policy-exploration/v1
Enforces total determinism, bounded exposure budgets, and uncertainty-aware scoring.

CRITICAL INVARIANTS:
- Exploitation strictly preserves the Phase 8.5 selection.
- Exploration candidate is selected only from the valid Phase 8.5 candidate slate.
- Current exploit candidate is excluded from exploration.
- Canonical NO_OFFER baseline is excluded from deliberate exploration.
- UCB score is used strictly for exploratory candidate ranking.
- Zero randomness; 100% reproducible.
"""

from typing import List, Dict, Optional, Tuple, Any
import structlog

from services.policy.schemas import PolicyCandidate, StrategyType
from services.selection.schemas import CandidateSelectionScore, PolicySelectionResult
from services.selection.ranking import STRATEGY_PRIORITY, CANONICAL_BASELINE_POLICY_ID
from services.exploration.schemas import (
    MerchantExplorationConfig,
    ExplorationReasonCode,
    ExplorationMode
)

logger = structlog.get_logger()


class ExplorationEngine:
    """Pure deterministic decision evaluator for Phase 8.7."""

    @classmethod
    def evaluate_exploration(
        cls,
        selection_result: PolicySelectionResult,
        candidate_map: Dict[str, PolicyCandidate],
        config: MerchantExplorationConfig,
        state_dict: Dict[str, Any],
        evidence_counts: Optional[Dict[str, int]] = None
    ) -> Tuple[ExplorationMode, Optional[PolicyCandidate], Optional[CandidateSelectionScore], int, ExplorationReasonCode, Dict[str, Any]]:
        """Deterministically evaluate whether to explore an alternative candidate or exploit.
        
        Returns:
            (mode, selected_candidate, selected_score, exposure_paise, reason_code, diagnostic_meta)
        """
        evidence = evidence_counts or {}
        exploit_policy_id = selection_result.selected_policy_id
        exploit_candidate = candidate_map.get(exploit_policy_id)

        # Find exploit score from selection result
        exploit_score: Optional[CandidateSelectionScore] = None
        for s in selection_result.ranked_candidates:
            if s.policy_id == exploit_policy_id:
                exploit_score = s
                break

        if not exploit_candidate or not exploit_score:
            # Malformed selection result -> fallback to exploit default
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_DEFAULT,
                {"error": "Exploit candidate not found in candidate map"}
            )

        # 1. Master Switch Check
        if not config.enabled:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_DISABLED,
                {"detail": "Exploration disabled by merchant configuration"}
            )

        # 2. Opportunity Budget Check
        opportunities_used = int(state_dict.get("opportunities_used", 0))
        if opportunities_used >= config.max_exploration_opportunities:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_BUDGET_EXHAUSTED,
                {
                    "opportunities_used": opportunities_used,
                    "max_opportunities": config.max_exploration_opportunities
                }
            )

        # 3. Consecutive Exploration Limit Check
        consecutive_used = int(state_dict.get("consecutive_explorations", 0))
        if consecutive_used >= config.max_consecutive_explorations:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_CONSECUTIVE_LIMIT_REACHED,
                {
                    "consecutive_explorations": consecutive_used,
                    "max_consecutive": config.max_consecutive_explorations
                }
            )

        # 4. Cumulative Economic Exposure Check
        exposure_used = int(state_dict.get("exposure_paise_used", 0))
        if exposure_used >= config.max_exposure_paise:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_EXPOSURE_LIMIT_REACHED,
                {
                    "exposure_paise_used": exposure_used,
                    "max_exposure_paise": config.max_exposure_paise
                }
            )

        # 5. Context Exposure Cap Check
        context_counts = state_dict.get("context_counts_json", {})
        buyer_context_key = selection_result.buyer_context_key
        if int(context_counts.get(buyer_context_key, 0)) >= config.max_context_exploration_count:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_CONTEXT_CAP_REACHED,
                {"buyer_context_key": buyer_context_key, "context_count": context_counts.get(buyer_context_key, 0)}
            )

        # 6. Benchmark Economic Baseline for Downside Exposure
        # Baseline is the best risk-free / learned alternative: max(exploit_prediction, baseline_NO_OFFER_prediction)
        baseline_pred_paise = selection_result.baseline_predicted_contribution_paise
        benchmark_contribution = max(exploit_score.predicted_contribution_paise, baseline_pred_paise)

        policy_counts = state_dict.get("policy_counts_json", {})
        eligible_alternatives: List[Tuple[PolicyCandidate, CandidateSelectionScore, int, int, float, int]] = []
        # Tuples: (candidate, score, ucb_paise, exposure_paise, unc_gap, obs_count)

        for s in selection_result.ranked_candidates:
            # Exclude current exploit candidate
            if s.policy_id == exploit_policy_id:
                continue

            # Exclude baseline NO_OFFER
            if s.is_baseline or s.policy_id == CANONICAL_BASELINE_POLICY_ID:
                continue

            # Candidate must be structurally eligible
            if not s.selection_eligible:
                continue

            cand = candidate_map.get(s.policy_id)
            if not cand:
                continue

            # Check per-policy exposure cap
            if int(policy_counts.get(s.policy_id, 0)) >= config.max_policy_exploration_count:
                continue

            # Compute exact pre-decision downside exposure
            candidate_exposure_paise = max(0, benchmark_contribution - s.predicted_contribution_paise)

            # Enforce per-decision exposure cap
            if candidate_exposure_paise > config.max_exposure_per_decision_paise:
                continue

            # Enforce remaining total window exposure budget
            if exposure_used + candidate_exposure_paise > config.max_exposure_paise:
                continue

            # Compute exploratory UCB score
            ucb_paise = s.predicted_contribution_paise + int(round(config.alpha_paise * s.uncertainty))
            unc_gap = s.uncertainty - exploit_score.uncertainty
            obs_count = int(evidence.get(s.policy_id, 0))

            eligible_alternatives.append((cand, s, ucb_paise, candidate_exposure_paise, unc_gap, obs_count))

        if not eligible_alternatives:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_NO_ALTERNATIVES,
                {"detail": "No eligible alternative candidates within budget and exposure limits"}
            )

        # 7. Evaluate Hardened Exploration Triggers
        # Trigger A: Uncertainty Advantage
        # - unc_gap >= min_uncertainty_gap
        # - Must have optimistic viability: ucb_paise >= baseline_pred_paise
        # Trigger B: Under-Observed Policy (Economically Eligible)
        # - obs_count < min_observations_threshold
        # - Optimistic Viability: ucb_paise >= baseline_pred_paise
        # - Bounded Deficit: s.predicted_contribution_paise >= baseline_pred_paise - max_underobserved_deficit_paise
        triggered_candidates: List[Tuple[PolicyCandidate, CandidateSelectionScore, int, int, float, int, str]] = []

        for cand, s, ucb_paise, exp_paise, unc_gap, obs_count in eligible_alternatives:
            is_optimistically_viable = (ucb_paise >= baseline_pred_paise)

            if unc_gap >= config.min_uncertainty_gap and is_optimistically_viable:
                triggered_candidates.append(
                    (cand, s, ucb_paise, exp_paise, unc_gap, obs_count, "UNCERTAINTY_ADVANTAGE")
                )
            elif obs_count < config.min_observations_threshold:
                # Under-observed economic eligibility check:
                # 1. Optimistic viability: ucb >= baseline
                # 2. Deficit not catastrophic: predicted >= baseline - max_deficit
                deficit_ok = (s.predicted_contribution_paise >= (baseline_pred_paise - config.max_underobserved_deficit_paise))
                if is_optimistically_viable and deficit_ok:
                    triggered_candidates.append(
                        (cand, s, ucb_paise, exp_paise, unc_gap, obs_count, "UNDER_OBSERVED_POLICY")
                    )

        if not triggered_candidates:
            return (
                ExplorationMode.EXPLOIT,
                exploit_candidate,
                exploit_score,
                0,
                ExplorationReasonCode.EXPLOIT_TRIGGER_NOT_SATISFIED,
                {
                    "detail": "None of the alternative candidates met uncertainty gap or economic eligibility triggers",
                    "exploit_uncertainty": exploit_score.uncertainty,
                    "min_gap_required": config.min_uncertainty_gap,
                    "min_obs_required": config.min_observations_threshold,
                    "max_deficit_paise": config.max_underobserved_deficit_paise
                }
            )

        # 8. Total Deterministic Ranking of Triggered Exploratory Candidates
        # Sorting hierarchy:
        # 1. ucb_score_paise DESC
        # 2. uncertainty DESC
        # 3. strategy_priority DESC
        # 4. policy_id ASC
        # 5. policy_version ASC
        def explore_sort_key(item):
            c, s, ucb_p, exp_p, unc_g, obs_c, trigger_name = item
            strat_prio = STRATEGY_PRIORITY.get(c.strategy_type, 0)
            return (
                -ucb_p,
                -s.uncertainty,
                -strat_prio,
                c.candidate_id,
                getattr(c, "policy_version", "merchant-policy/v1") or "merchant-policy/v1"
            )

        triggered_candidates.sort(key=explore_sort_key)
        best_cand, best_score, best_ucb, best_exposure, best_unc_gap, best_obs, trigger_name = triggered_candidates[0]

        reason = (
            ExplorationReasonCode.EXPLORE_UNCERTAINTY_ADVANTAGE
            if trigger_name == "UNCERTAINTY_ADVANTAGE"
            else ExplorationReasonCode.EXPLORE_UNDER_OBSERVED_POLICY
        )

        diagnostic = {
            "trigger_name": trigger_name,
            "exploit_policy_id": exploit_policy_id,
            "exploit_prediction_paise": exploit_score.predicted_contribution_paise,
            "exploit_uncertainty": exploit_score.uncertainty,
            "explored_policy_id": best_cand.candidate_id,
            "explored_prediction_paise": best_score.predicted_contribution_paise,
            "explored_uncertainty": best_score.uncertainty,
            "explored_ucb_paise": best_ucb,
            "exploration_exposure_paise": best_exposure,
            "uncertainty_gap": best_unc_gap,
            "observations_count": best_obs
        }

        return (
            ExplorationMode.EXPLORE,
            best_cand,
            best_score,
            best_exposure,
            reason,
            diagnostic
        )
