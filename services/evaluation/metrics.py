"""Deterministic Metric Calculator for Phase 8.9 Closed-Loop Learning Evaluation.

Contracts:
- closed-loop-evaluation/v1
- merchant-reward/v1
- contribution-formula/v1

Enforces:
- Strict integer paise arithmetic for economic totals and ECPS.
- Exact denominator retention (zero-contribution trials retained in sample).
- Robust 95% confidence intervals and standard deviation calculations.
- Objective PASS/FAIL/INCONCLUSIVE outcome determination.
"""

import math
from typing import List, Tuple, Optional
from services.evaluation.schemas import (
    EvaluationMetricSet,
    HoldoutMetricSet,
    ClosedLoopEvaluationConfig,
    EvaluationOutcome
)


class EvaluationMetricCalculator:
    """Pure deterministic statistical and economic metric evaluator."""

    @staticmethod
    def calculate_ecps(contributions_paise: List[int]) -> int:
        """Expected Contribution per AI Shopper (ECPS) in integer paise.
        
        Formula: sum(contributions) / N
        Zero-contribution trials are retained in denominator.
        """
        if not contributions_paise:
            return 0
        return int(round(sum(contributions_paise) / len(contributions_paise)))

    @staticmethod
    def calculate_std_deviation(contributions_paise: List[int]) -> float:
        """Sample standard deviation in integer paise."""
        n = len(contributions_paise)
        if n <= 1:
            return 0.0
        mean = sum(contributions_paise) / n
        variance = sum((x - mean) ** 2 for x in contributions_paise) / (n - 1)
        return float(round(math.sqrt(variance), 2))

    @staticmethod
    def calculate_confidence_interval_95(contributions_paise: List[int]) -> Tuple[float, float]:
        """95% Confidence Interval for mean contribution in paise."""
        n = len(contributions_paise)
        if n <= 1:
            val = float(contributions_paise[0]) if n == 1 else 0.0
            return (val, val)
        mean = sum(contributions_paise) / n
        std = EvaluationMetricCalculator.calculate_std_deviation(contributions_paise)
        stderr = std / math.sqrt(n)
        margin = 1.96 * stderr
        return (round(mean - margin, 2), round(mean + margin, 2))

    @staticmethod
    def calculate_relative_delta(learned_ecps: int, baseline_ecps: int) -> Optional[float]:
        """Percentage delta relative to baseline if baseline > 0."""
        if baseline_ecps > 0:
            return round(((learned_ecps - baseline_ecps) / baseline_ecps) * 100.0, 2)
        return None

    @classmethod
    def assemble_metric_set(
        cls,
        contributions_paise: List[int],
        baseline_contributions_paise: List[int],
        selections: List[bool],
        conversions: List[bool],
        exploration_modes: List[str],
        exposures_paise: List[int],
        safety_rejections: List[bool],
        fallbacks_to_exploit: List[bool],
        model_updates_count: int
    ) -> EvaluationMetricSet:
        """Aggregate opportunity step vectors into a complete EvaluationMetricSet."""
        sample_size = len(contributions_paise)
        learned_ecps = cls.calculate_ecps(contributions_paise)
        baseline_ecps = cls.calculate_ecps(baseline_contributions_paise)
        absolute_delta = learned_ecps - baseline_ecps
        relative_delta = cls.calculate_relative_delta(learned_ecps, baseline_ecps)

        selection_rate = round(sum(1 for s in selections if s) / max(sample_size, 1), 4)
        conversion_rate = round(sum(1 for c in conversions if c) / max(sample_size, 1), 4)
        exploration_rate = round(sum(1 for m in exploration_modes if m == "EXPLORE") / max(sample_size, 1), 4)
        safety_rejection_rate = round(sum(1 for sr in safety_rejections if sr) / max(sample_size, 1), 4)
        fallback_rate = round(sum(1 for fb in fallbacks_to_exploit if fb) / max(sample_size, 1), 4)
        exposure_consumed = sum(exposures_paise)
        std_dev = cls.calculate_std_deviation(contributions_paise)
        ci_95 = cls.calculate_confidence_interval_95(contributions_paise)

        return EvaluationMetricSet(
            sample_size=sample_size,
            total_opportunities=sample_size,
            baseline_ecps_paise=baseline_ecps,
            learned_ecps_paise=learned_ecps,
            absolute_delta_paise=absolute_delta,
            relative_delta=relative_delta,
            selection_rate=selection_rate,
            conversion_rate=conversion_rate,
            exploration_rate=exploration_rate,
            exposure_paise_consumed=exposure_consumed,
            safety_rejection_rate=safety_rejection_rate,
            fallback_to_exploit_rate=fallback_rate,
            model_updates_count=model_updates_count,
            std_deviation_paise=std_dev,
            confidence_interval_95_paise=ci_95
        )

    @classmethod
    def assemble_holdout_metrics(
        cls,
        holdout_contributions_paise: List[int],
        holdout_baseline_contributions_paise: List[int],
        holdout_selections: List[bool],
        holdout_safety_rejections: List[bool]
    ) -> HoldoutMetricSet:
        """Compute generalization metrics on the frozen holdout set."""
        sample_size = len(holdout_contributions_paise)
        holdout_ecps = cls.calculate_ecps(holdout_contributions_paise)
        baseline_ecps = cls.calculate_ecps(holdout_baseline_contributions_paise)
        absolute_delta = holdout_ecps - baseline_ecps
        relative_delta = cls.calculate_relative_delta(holdout_ecps, baseline_ecps)
        selection_rate = round(sum(1 for s in holdout_selections if s) / max(sample_size, 1), 4)
        safety_rate = round(sum(1 for sr in holdout_safety_rejections if sr) / max(sample_size, 1), 4)

        return HoldoutMetricSet(
            holdout_sample_size=sample_size,
            holdout_ecps_paise=holdout_ecps,
            baseline_ecps_paise=baseline_ecps,
            absolute_delta_paise=absolute_delta,
            relative_delta=relative_delta,
            holdout_selection_rate=selection_rate,
            holdout_safety_rejection_rate=safety_rate
        )

    @classmethod
    def determine_evaluation_outcome(
        cls,
        summary: EvaluationMetricSet,
        holdout: HoldoutMetricSet,
        config: ClosedLoopEvaluationConfig
    ) -> Tuple[EvaluationOutcome, List[str]]:
        """Deterministically determine PASS, FAIL, INCONCLUSIVE, or INSUFFICIENT_EVIDENCE."""
        failure_reasons: List[str] = []

        # 1. Sample Size Check
        if summary.sample_size < 20:
            failure_reasons.append(f"Sample size {summary.sample_size} < 20 minimum required for closed-loop evaluation.")
            return EvaluationOutcome.INSUFFICIENT_EVIDENCE, failure_reasons

        # 2. Safety Rejection Threshold Check
        max_allowed_safety_rejections = (config.max_tolerated_safety_rejections_percent / 100.0)
        if summary.safety_rejection_rate > max_allowed_safety_rejections:
            failure_reasons.append(
                f"Safety rejection rate {summary.safety_rejection_rate:.1%} exceeds maximum tolerated {max_allowed_safety_rejections:.1%}."
            )

        # 3. Learning Uplift Check
        training_improved = summary.absolute_delta_paise >= config.min_ecps_improvement_paise
        holdout_non_negative = holdout.absolute_delta_paise >= 0

        if not training_improved:
            failure_reasons.append(
                f"Learned ECPS {summary.learned_ecps_paise} paise did not satisfy minimum uplift over baseline {summary.baseline_ecps_paise} paise."
            )

        if config.require_holdout_non_negative and not holdout_non_negative:
            failure_reasons.append(
                f"Holdout ECPS {holdout.holdout_ecps_paise} paise underperformed baseline {holdout.baseline_ecps_paise} paise (negative generalization)."
            )

        # Outcome Logic
        if not failure_reasons:
            return EvaluationOutcome.PASS, []

        if training_improved and not holdout_non_negative:
            # Overfitting: improved training but degraded holdout
            return EvaluationOutcome.FAIL, failure_reasons

        if not training_improved and holdout.absolute_delta_paise == 0:
            return EvaluationOutcome.INCONCLUSIVE, failure_reasons

        return EvaluationOutcome.FAIL, failure_reasons
