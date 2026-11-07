"""Pure Deterministic Policy Promotion Evaluator for Phase 8.8 & Phase 8.8.1.

Contracts:
- policy-lifecycle/v1
- promotion-policy/v1

Enforces evidence-gated evaluation:
- Explicit Evidence-Strength Hierarchy: CONTROLLED_EXPERIMENT vs OBSERVATIONAL_HISTORY
- Sample size sufficiency from Phase 8.3 memory
- Current-effective non-superseded population integrity
- Strict policy version integrity (no cross-version evidence pooling)
- Recency & temporal drift defense (lookback window, future evidence rejection)
- Observational concentration limit & context diversity
- Economic viability (positive observed contribution)
- Baseline superiority (outperforms NO_OFFER reserve)
- Zero historical safety violations
- Phase 7 experiment evaluation criteria when experimental evidence is referenced
"""

from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional

from domain.models import PolicyMemoryRecord
from services.experiments.schemas import ExperimentResult, ExperimentStatus, EvidenceStatus, VariantType
from services.lifecycle.schemas import (
    PromotionPolicyConfig,
    PromotionFailureCode,
    PromotionEvidenceType
)


class PolicyPromotionEvaluator:
    """Pure deterministic evaluator checking whether a policy satisfies promotion criteria."""

    @classmethod
    def evaluate_promotion_eligibility(
        cls,
        candidate_policy_id: str,
        config: PromotionPolicyConfig,
        memory_records: List[PolicyMemoryRecord],
        baseline_records: List[PolicyMemoryRecord],
        candidate_policy_version: str = "merchant-policy/v1",
        experiment_result: Optional[ExperimentResult] = None,
        evaluation_time: Optional[datetime] = None
    ) -> Tuple[bool, List[PromotionFailureCode], Dict[str, Any]]:
        """Deterministically evaluate candidate against all promotion criteria.
        
        Returns:
            (is_eligible, failure_codes, evidence_summary)
        """
        failure_codes: List[PromotionFailureCode] = []

        if evaluation_time is None:
            evaluation_time = datetime.now(timezone.utc)
        elif evaluation_time.tzinfo is None:
            evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)

        # Helper for extracting economic contribution
        def _get_contribution(rec: PolicyMemoryRecord) -> int:
            return getattr(rec, "reward_contribution_paise", getattr(rec, "observed_contribution_paise", 0))

        # ---------------------------------------------------------------------
        # 1. Population Integrity & Policy Version Integrity
        # ---------------------------------------------------------------------
        all_cand_records = [r for r in memory_records if r.policy_id == candidate_policy_id]
        version_matching_records = [
            r for r in all_cand_records
            if getattr(r, "policy_version", "merchant-policy/v1") == candidate_policy_version
        ]

        # Version integrity: records exist for candidate_id but none for candidate_version
        if len(all_cand_records) > 0 and len(version_matching_records) == 0:
            failure_codes.append(PromotionFailureCode.POLICY_VERSION_MISMATCH)

        # Current-effective records only (exclude superseded observations)
        non_superseded = [
            r for r in version_matching_records
            if getattr(r, "is_current", True) is not False and getattr(r, "superseded_by", None) is None
        ]
        superseded_count = len(version_matching_records) - len(non_superseded)

        # Filter learning_eligible and admissible records
        admissible_learning = [
            r for r in non_superseded
            if r.learning_eligible and r.is_admissible
        ]

        # Check for future observations (cannot use future evidence)
        future_records: List[PolicyMemoryRecord] = []
        valid_time_records: List[PolicyMemoryRecord] = []
        for r in admissible_learning:
            obs_time = r.observed_at
            if obs_time is not None:
                if obs_time.tzinfo is None:
                    obs_time = obs_time.replace(tzinfo=timezone.utc)
                if obs_time > evaluation_time:
                    future_records.append(r)
                else:
                    valid_time_records.append(r)
            else:
                valid_time_records.append(r)

        if future_records:
            failure_codes.append(PromotionFailureCode.FUTURE_EVIDENCE_REJECTED)

        # Deduplicate by opportunity_id to ensure one opportunity does not contribute twice
        deduped_cand_map: Dict[str, PolicyMemoryRecord] = {}
        for r in valid_time_records:
            opp_id = getattr(r, "opportunity_id", None) or r.id
            if opp_id not in deduped_cand_map:
                deduped_cand_map[opp_id] = r
            else:
                existing = deduped_cand_map[opp_id]
                if r.observed_at and existing.observed_at and r.observed_at > existing.observed_at:
                    deduped_cand_map[opp_id] = r

        unique_candidates = list(deduped_cand_map.values())

        # Recency filtering: exclude records outside recency window
        recency_cutoff = evaluation_time - timedelta(days=config.recency_window_days)
        qualifying_records: List[PolicyMemoryRecord] = []
        stale_records: List[PolicyMemoryRecord] = []
        for r in unique_candidates:
            obs_time = r.observed_at
            if obs_time is not None:
                if obs_time.tzinfo is None:
                    obs_time = obs_time.replace(tzinfo=timezone.utc)
                if obs_time < recency_cutoff:
                    stale_records.append(r)
                else:
                    qualifying_records.append(r)
            else:
                qualifying_records.append(r)

        sample_size = len(qualifying_records)

        # ---------------------------------------------------------------------
        # 2. Historical Safety Violations Check
        # ---------------------------------------------------------------------
        safety_violations = sum(
            1 for r in non_superseded
            if getattr(r, "is_safety_violation", False) or getattr(r, "reward_state", None) == "REWARD_GUARDRAIL_VIOLATION"
        )
        if safety_violations > config.max_tolerated_safety_violations:
            failure_codes.append(PromotionFailureCode.GUARDRAIL_BREACH)

        # ---------------------------------------------------------------------
        # 3. Evidence-Strength Hierarchy & Path Determination
        # ---------------------------------------------------------------------
        evidence_type: Optional[PromotionEvidenceType] = None
        exp_summary: Optional[Dict[str, Any]] = None
        observational_bias_warning: Optional[str] = None
        min_required_sample: int = config.min_learning_opportunities

        if config.require_controlled_experiment:
            min_required_sample = config.min_learning_opportunities
            if not experiment_result:
                failure_codes.append(PromotionFailureCode.EXPERIMENT_NOT_FOUND)
            else:
                evidence_type = PromotionEvidenceType.CONTROLLED_EXPERIMENT
                exp_summary = {
                    "experiment_id": experiment_result.experiment_id,
                    "status": experiment_result.status.value,
                    "evidence_status": experiment_result.evidence_status.value,
                    "winner": experiment_result.winner.value if experiment_result.winner else None
                }
                if experiment_result.status != ExperimentStatus.COMPLETED:
                    failure_codes.append(PromotionFailureCode.INCONCLUSIVE_EXPERIMENT)
                if experiment_result.evidence_status != EvidenceStatus.SUFFICIENT_EVIDENCE:
                    failure_codes.append(PromotionFailureCode.INCONCLUSIVE_EXPERIMENT)
                if experiment_result.winner != VariantType.TREATMENT:
                    failure_codes.append(PromotionFailureCode.EXPERIMENT_NOT_WON)
                if any(not g.passed for g in (experiment_result.guardrail_results or [])):
                    failure_codes.append(PromotionFailureCode.GUARDRAIL_BREACH)

        elif experiment_result is not None:
            # Controlled experiment provided (even if not strictly mandatory)
            evidence_type = PromotionEvidenceType.CONTROLLED_EXPERIMENT
            min_required_sample = config.min_learning_opportunities
            exp_summary = {
                "experiment_id": experiment_result.experiment_id,
                "status": experiment_result.status.value,
                "evidence_status": experiment_result.evidence_status.value,
                "winner": experiment_result.winner.value if experiment_result.winner else None
            }
            if experiment_result.status != ExperimentStatus.COMPLETED:
                failure_codes.append(PromotionFailureCode.INCONCLUSIVE_EXPERIMENT)
            if experiment_result.evidence_status in (EvidenceStatus.INSUFFICIENT_SAMPLE, EvidenceStatus.INCONCLUSIVE):
                failure_codes.append(PromotionFailureCode.INCONCLUSIVE_EXPERIMENT)
            if experiment_result.evidence_status == EvidenceStatus.GUARDRAIL_FAILURE:
                failure_codes.append(PromotionFailureCode.GUARDRAIL_BREACH)
            if experiment_result.winner != VariantType.TREATMENT:
                failure_codes.append(PromotionFailureCode.EXPERIMENT_NOT_WON)
            if any(not g.passed for g in (experiment_result.guardrail_results or [])):
                failure_codes.append(PromotionFailureCode.GUARDRAIL_BREACH)

        else:
            # Observational history path
            if not config.allow_observational_promotion:
                failure_codes.append(PromotionFailureCode.OBSERVATIONAL_PROMOTION_DISALLOWED)
                min_required_sample = config.effective_observational_min_sample
            else:
                evidence_type = PromotionEvidenceType.OBSERVATIONAL_HISTORY
                min_required_sample = config.effective_observational_min_sample
                observational_bias_warning = (
                    "Observational evidence only. Subject to historical selection bias. "
                    "Does not establish causal superiority or guaranteed uplift."
                )

        # ---------------------------------------------------------------------
        # 4. Sample Size Check
        # ---------------------------------------------------------------------
        if sample_size < min_required_sample:
            # If historical records exist but are excluded due to staleness
            if len(unique_candidates) >= min_required_sample and len(stale_records) > 0:
                failure_codes.append(PromotionFailureCode.STALE_EVIDENCE)
            else:
                failure_codes.append(PromotionFailureCode.INSUFFICIENT_SAMPLE_SIZE)

        # ---------------------------------------------------------------------
        # 5. Observed Contribution Check
        # ---------------------------------------------------------------------
        if sample_size > 0:
            total_contribution_paise = sum(_get_contribution(r) for r in qualifying_records)
            mean_contribution_paise = total_contribution_paise / sample_size
        else:
            total_contribution_paise = 0
            mean_contribution_paise = 0.0

        if sample_size > 0 and mean_contribution_paise < config.min_positive_contribution_paise:
            failure_codes.append(PromotionFailureCode.NEGATIVE_CONTRIBUTION)

        # ---------------------------------------------------------------------
        # 6. Baseline Superiority Check
        # ---------------------------------------------------------------------
        base_qualifying: List[PolicyMemoryRecord] = []
        for r in baseline_records:
            if not (r.learning_eligible and r.is_admissible):
                continue
            if getattr(r, "is_current", True) is False or getattr(r, "superseded_by", None) is not None:
                continue
            obs_time = r.observed_at
            if obs_time is not None:
                if obs_time.tzinfo is None:
                    obs_time = obs_time.replace(tzinfo=timezone.utc)
                if obs_time < recency_cutoff or obs_time > evaluation_time:
                    continue
            base_qualifying.append(r)

        base_deduped_map = {getattr(r, "opportunity_id", None) or r.id: r for r in base_qualifying}
        base_deduped = list(base_deduped_map.values())

        if base_deduped:
            base_mean_paise = sum(_get_contribution(r) for r in base_deduped) / len(base_deduped)
        else:
            base_mean_paise = 0.0

        improvement_over_baseline_paise = mean_contribution_paise - base_mean_paise
        if sample_size > 0 and improvement_over_baseline_paise < config.min_improvement_over_baseline_paise:
            failure_codes.append(PromotionFailureCode.NO_IMPROVEMENT_OVER_BASELINE)

        # ---------------------------------------------------------------------
        # 7. Observational-Specific Conservative Checks (Concentration & Diversity)
        # ---------------------------------------------------------------------
        concentration_stats: Dict[str, Any] = {}
        context_stats: Dict[str, Any] = {}

        if evidence_type == PromotionEvidenceType.OBSERVATIONAL_HISTORY and sample_size > 0:
            # Concentration check
            pos_contribs = [_get_contribution(r) for r in qualifying_records if _get_contribution(r) > 0]
            sum_pos = sum(pos_contribs)
            if sum_pos > 0 and len(qualifying_records) > 1:
                max_contrib = max(pos_contribs)
                share = max_contrib / sum_pos
                if share > config.max_opportunity_contribution_share:
                    failure_codes.append(PromotionFailureCode.OBSERVATIONAL_CONCENTRATION_EXCEEDED)
                concentration_stats = {
                    "max_single_opp_share": round(share, 4),
                    "threshold": config.max_opportunity_contribution_share
                }
            else:
                concentration_stats = {
                    "max_single_opp_share": 1.0 if sum_pos > 0 else 0.0,
                    "threshold": config.max_opportunity_contribution_share
                }

            # Context diversity check
            distinct_contexts = set(
                r.buyer_context_key for r in qualifying_records
                if getattr(r, "buyer_context_key", None)
            )
            if len(distinct_contexts) < config.min_distinct_contexts:
                failure_codes.append(PromotionFailureCode.INSUFFICIENT_CONTEXT_DIVERSITY)

            context_stats = {
                "distinct_contexts_count": len(distinct_contexts),
                "context_distribution": {
                    ctx: sum(1 for r in qualifying_records if r.buyer_context_key == ctx)
                    for ctx in distinct_contexts
                }
            }

        # ---------------------------------------------------------------------
        # 8. Snapshot Assembly
        # ---------------------------------------------------------------------
        evidence_summary = {
            "evidence_type": evidence_type.value if evidence_type else None,
            "observational_bias_warning": observational_bias_warning,
            "candidate_policy_id": candidate_policy_id,
            "candidate_policy_version": candidate_policy_version,
            "sample_size": sample_size,
            "min_required_sample": min_required_sample,
            "raw_candidate_records_count": len(all_cand_records),
            "version_matching_records_count": len(version_matching_records),
            "superseded_records_count": superseded_count,
            "stale_records_count": len(stale_records),
            "future_records_count": len(future_records),
            "recency_window_days": config.recency_window_days,
            "recency_cutoff_iso": recency_cutoff.isoformat(),
            "evaluation_time_iso": evaluation_time.isoformat(),
            "total_observed_contribution_paise": total_contribution_paise,
            "mean_observed_contribution_paise": mean_contribution_paise,
            "baseline_mean_contribution_paise": base_mean_paise,
            "improvement_over_baseline_paise": improvement_over_baseline_paise,
            "safety_violations_count": safety_violations,
            "concentration": concentration_stats,
            "context_coverage": context_stats,
            "controlled_experiment": exp_summary
        }

        # Deduplicate failure codes preserving order
        unique_failures: List[PromotionFailureCode] = []
        for code in failure_codes:
            if code not in unique_failures:
                unique_failures.append(code)

        is_eligible = (len(unique_failures) == 0)
        return is_eligible, unique_failures, evidence_summary
