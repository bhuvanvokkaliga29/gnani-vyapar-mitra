"""Deterministic Learned Policy Candidate Ranking & Selection Engine.

Contract: policy-selection/v1
Enforces total deterministic ordering:
1. predicted_contribution_paise DESC (Primary: pure learned predicted contribution)
2. strategy_priority DESC (Secondary: deterministic commercial strategy hierarchy)
3. policy_id ASC (Tertiary: deterministic candidate identity tie-breaker)
4. policy_version ASC (Quaternary: deterministic version tie-breaker)

CRITICAL INVARIANTS:
- Selection score = predicted contribution in paise.
- composite_score is EXCLUDED from tie-breaking (no secondary multi-factor optimization signals).
- UCB score is NEVER used for candidate ranking or selection.
- Predictive uncertainty is NEVER used as a tie-breaker.
- Mandatory NO_OFFER reserve baseline comparison: if best_offer <= NO_OFFER, NO_OFFER is selected.
- Pure pre-decision evaluation; zero execution authority.
"""

from typing import List, Tuple, Optional, Dict, Any
from domain.intent_schemas import BuyerIntent, ConfidenceLevel
from domain.commerce_schemas import MerchantCommerceContext
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus
)
from services.learning.algorithm import ContextualLinearUCB
from services.learning.features import PolicyFeatureExtractor
from services.selection.schemas import CandidateSelectionScore
from services.selection.errors import EmptyCandidateSetError, MalformedCandidateError


# Standard strategy priority for secondary tie-breaking
STRATEGY_PRIORITY: Dict[StrategyType, int] = {
    StrategyType.COMPLEMENTARY_BUNDLE: 7,
    StrategyType.VALUE_BUNDLE: 6,
    StrategyType.SINGLE_PRODUCT: 5,
    StrategyType.BOUNDED_DISCOUNT: 4,
    StrategyType.ALTERNATIVE_PRODUCT: 3,
    StrategyType.NON_PRICE_INCENTIVE: 2,
    StrategyType.NO_OFFER: 1,
}

CANONICAL_BASELINE_POLICY_ID = "cand_base_no_offer"


class PolicyCandidateSelector:
    """Deterministic selection engine for Phase 8.5."""

    @staticmethod
    def create_canonical_no_offer_baseline() -> PolicyCandidate:
        """Construct canonical reserve NO_OFFER baseline."""
        return PolicyCandidate(
            candidate_id=CANONICAL_BASELINE_POLICY_ID,
            strategy_type=StrategyType.NO_OFFER,
            product_ids=[],
            rationale="Default commercial reserve baseline (no offer).",
            confidence=ConfidenceLevel.HIGH,
            validation_status=CandidateValidationStatus.APPROVED
        )

    @classmethod
    def evaluate_and_rank_candidates(
        cls,
        candidates: List[PolicyCandidate],
        intent: BuyerIntent,
        buyer_context_key: str,
        model: ContextualLinearUCB,
        commerce_context: Optional[MerchantCommerceContext] = None
    ) -> Tuple[CandidateSelectionScore, CandidateSelectionScore, List[CandidateSelectionScore], str]:
        """Rank candidates deterministically and select the currently preferred policy.
        
        Returns:
            Tuple of:
            - selected_candidate_score
            - baseline_candidate_score
            - full_ranked_slate
            - selection_reason
        """
        if not candidates:
            raise EmptyCandidateSetError("Cannot perform policy selection on an empty candidate set.")

        # 1. Guarantee presence of NO_OFFER baseline
        has_baseline = any(c.strategy_type == StrategyType.NO_OFFER for c in candidates)
        working_candidates = list(candidates)
        if not has_baseline:
            working_candidates.append(cls.create_canonical_no_offer_baseline())

        # 2. Structural validation & model prediction for every candidate
        evaluated_records = []
        for cand in working_candidates:
            if not cand.candidate_id or not isinstance(cand.candidate_id, str):
                raise MalformedCandidateError("Candidate missing valid string candidate_id.")

            is_baseline = (cand.strategy_type == StrategyType.NO_OFFER)
            policy_version = getattr(cand, "policy_version", "merchant-policy/v1") or "merchant-policy/v1"

            # Check structural validation status
            is_rejected = (cand.validation_status == CandidateValidationStatus.REJECTED)
            if is_rejected:
                evaluated_records.append({
                    "candidate": cand,
                    "policy_id": cand.candidate_id,
                    "policy_version": policy_version,
                    "predicted_contribution_paise": 0,
                    "uncertainty": 0.0,
                    "is_baseline": is_baseline,
                    "selection_eligible": False,
                    "exclusion_reason": "VALIDATION_REJECTED",
                    "composite_score": 0.0,
                    "strategy_priority": STRATEGY_PRIORITY.get(cand.strategy_type, 0)
                })
                continue

            # Extract features and predict using Phase 8.4 model
            try:
                x = PolicyFeatureExtractor.extract(
                    intent=intent,
                    candidate=cand,
                    economics=getattr(cand, "deterministic_economics", None),
                    buyer_context_key=buyer_context_key
                )
                pred_paise, unc, _ = model.predict(x)
            except Exception as e:
                # If feature extraction or prediction fails, mark ineligible
                evaluated_records.append({
                    "candidate": cand,
                    "policy_id": cand.candidate_id,
                    "policy_version": policy_version,
                    "predicted_contribution_paise": 0,
                    "uncertainty": 0.0,
                    "is_baseline": is_baseline,
                    "selection_eligible": False,
                    "exclusion_reason": f"PREDICTION_FAILED: {str(e)}",
                    "strategy_priority": STRATEGY_PRIORITY.get(cand.strategy_type, 0)
                })
                continue

            evaluated_records.append({
                "candidate": cand,
                "policy_id": cand.candidate_id,
                "policy_version": policy_version,
                "predicted_contribution_paise": pred_paise,
                "uncertainty": unc,
                "is_baseline": is_baseline,
                "selection_eligible": True,
                "exclusion_reason": None,
                "strategy_priority": STRATEGY_PRIORITY.get(cand.strategy_type, 0)
            })

        # 3. Deterministic Sort
        # Primary: predicted_contribution_paise DESC
        # Secondary: strategy_priority DESC
        # Tertiary: policy_id ASC
        # Quaternary: policy_version ASC
        # NOTE: uncertainty/UCB is NEVER in the sort key!
        # Pass 1: sort by ascending identifiers (policy_id ASC, policy_version ASC)
        evaluated_records.sort(key=lambda r: (r["policy_id"], r["policy_version"]))
        # Pass 2: stable sort by descending primary economic prediction and strategy priority
        evaluated_records.sort(
            key=lambda r: (
                1 if r["selection_eligible"] else 0,
                r["predicted_contribution_paise"],
                r["strategy_priority"]
            ),
            reverse=True
        )

        # 4. Assign 1-indexed ranks and construct CandidateSelectionScore
        ranked_slate: List[CandidateSelectionScore] = []
        for rank_idx, rec in enumerate(evaluated_records, start=1):
            ranked_slate.append(
                CandidateSelectionScore(
                    policy_id=rec["policy_id"],
                    policy_version=rec["policy_version"],
                    predicted_contribution_paise=rec["predicted_contribution_paise"],
                    uncertainty=rec["uncertainty"],
                    rank=rank_idx,
                    is_baseline=rec["is_baseline"],
                    selection_eligible=rec["selection_eligible"],
                    exclusion_reason=rec["exclusion_reason"]
                )
            )

        # 5. Baseline Comparison Rule
        # Locate baseline in ranked slate
        baseline_score = next((c for c in ranked_slate if c.is_baseline), None)
        if not baseline_score:
            # Fallback (should never happen due to step 1)
            baseline_score = ranked_slate[-1]

        eligible_candidates = [c for c in ranked_slate if c.selection_eligible]
        non_baseline_candidates = [c for c in eligible_candidates if not c.is_baseline]

        if not non_baseline_candidates:
            selected_score = baseline_score
            selection_reason = "NO_OFFER_BASELINE_ONLY"
        else:
            best_offer = non_baseline_candidates[0]
            # Rule: if best_offer <= baseline, select NO_OFFER
            if best_offer.predicted_contribution_paise <= baseline_score.predicted_contribution_paise:
                selected_score = baseline_score
                if best_offer.predicted_contribution_paise < baseline_score.predicted_contribution_paise:
                    selection_reason = "NO_OFFER_BASELINE_DOMINATES"
                else:
                    selection_reason = "NO_VALID_POSITIVE_OFFER"
            else:
                selected_score = best_offer
                # Check if multiple non-baseline candidates tied for top prediction
                tied_top = [
                    c for c in non_baseline_candidates
                    if c.predicted_contribution_paise == best_offer.predicted_contribution_paise
                ]
                if len(tied_top) > 1:
                    selection_reason = "DETERMINISTIC_TIE_BREAK"
                else:
                    selection_reason = "HIGHEST_PREDICTED_CONTRIBUTION"

        return selected_score, baseline_score, ranked_slate, selection_reason
