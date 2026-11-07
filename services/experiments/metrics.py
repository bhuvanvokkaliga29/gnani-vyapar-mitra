"""Experiment Metric Engine: Deterministic computation of sample sizes, selection rates, contribution, and deltas."""

from typing import List, Dict, Tuple
from services.experiments.schemas import (
    ExperimentObservation,
    VariantMetrics,
    MetricDelta,
    ExperimentGuardrail,
    GuardrailType,
    GuardrailResult
)


class ExperimentMetricEngine:
    """Computes exact, deterministic commercial metrics from experiment observations."""

    @staticmethod
    def aggregate_variant_metrics(observations: List[ExperimentObservation]) -> VariantMetrics:
        """Aggregate raw decision instance observations for a single variant arm."""
        sample_size = len(observations)
        if sample_size == 0:
            return VariantMetrics()

        selection_count = sum(1 for obs in observations if obs.is_selected)
        selection_rate = round(selection_count / sample_size, 4)

        order_creation_count = sum(
            1 for obs in observations if (obs.order_id is not None or obs.razorpay_order_id is not None)
        )
        order_creation_rate = round(order_creation_count / sample_size, 4)

        payment_success_count = sum(
            1 for obs in observations if obs.payment_outcome == "CAPTURED"
        )
        payment_success_rate = (
            round(payment_success_count / order_creation_count, 4) if order_creation_count > 0 else 0.0
        )

        total_revenue_paise = sum(obs.revenue_paise for obs in observations)
        conversion_units = payment_success_count if payment_success_count > 0 else selection_count
        aov_paise = int(total_revenue_paise / conversion_units) if conversion_units > 0 else 0

        total_contribution_paise = sum(obs.contribution_paise for obs in observations)
        expected_contribution_per_shopper_paise = int(total_contribution_paise / sample_size)

        selected_margins = [obs.margin_percent for obs in observations if obs.is_selected]
        avg_margin = (
            round(sum(selected_margins) / len(selected_margins), 2) if selected_margins else 0.0
        )

        guardrail_violation_count = sum(len(obs.guardrail_violations) for obs in observations)

        return VariantMetrics(
            sample_size=sample_size,
            selection_count=selection_count,
            selection_rate=selection_rate,
            order_creation_count=order_creation_count,
            order_creation_rate=order_creation_rate,
            payment_success_count=payment_success_count,
            payment_success_rate=payment_success_rate,
            total_revenue_paise=total_revenue_paise,
            aov_paise=aov_paise,
            total_contribution_paise=total_contribution_paise,
            expected_contribution_per_shopper_paise=expected_contribution_per_shopper_paise,
            average_margin_percent=avg_margin,
            guardrail_violation_count=guardrail_violation_count
        )

    @staticmethod
    def compute_metric_deltas(
        control_metrics: VariantMetrics,
        treatment_metrics: VariantMetrics
    ) -> Dict[str, MetricDelta]:
        """Calculate absolute and relative deltas between Treatment and Control."""
        deltas = {}

        metrics_map = [
            ("SELECTION_RATE", control_metrics.selection_rate, treatment_metrics.selection_rate, True),
            ("EXPECTED_CONTRIBUTION_PER_SHOPPER", float(control_metrics.expected_contribution_per_shopper_paise), float(treatment_metrics.expected_contribution_per_shopper_paise), True),
            ("AOV_PAISE", float(control_metrics.aov_paise), float(treatment_metrics.aov_paise), True),
            ("MARGIN_PERCENT", control_metrics.average_margin_percent, treatment_metrics.average_margin_percent, True),
            ("ORDER_CREATION_RATE", control_metrics.order_creation_rate, treatment_metrics.order_creation_rate, True),
            ("PAYMENT_SUCCESS_RATE", control_metrics.payment_success_rate, treatment_metrics.payment_success_rate, True),
        ]

        for name, ctrl_val, treat_val, higher_is_better in metrics_map:
            abs_diff = round(treat_val - ctrl_val, 4)
            rel_diff = None
            if ctrl_val != 0:
                rel_diff = round((abs_diff / ctrl_val) * 100.0, 2)

            improved = (abs_diff > 0) if higher_is_better else (abs_diff < 0)

            deltas[name] = MetricDelta(
                metric_name=name,
                control_value=round(ctrl_val, 4),
                treatment_value=round(treat_val, 4),
                absolute_difference=abs_diff,
                relative_difference_percent=rel_diff,
                directionally_improved=improved
            )

        return deltas

    @staticmethod
    def evaluate_guardrails(
        guardrails: List[ExperimentGuardrail],
        treatment_metrics: VariantMetrics,
        policy_diff_margin: float = 0.0
    ) -> List[GuardrailResult]:
        """Evaluate each guardrail against treatment performance and policy diff."""
        results = []

        for g in guardrails:
            if g.guardrail_type == GuardrailType.MIN_MARGIN_PERCENT:
                # Target margin threshold, e.g. 0.25 (25%)
                threshold_pct = g.threshold_value * 100.0 if g.threshold_value <= 1.0 else g.threshold_value
                observed = treatment_metrics.average_margin_percent if treatment_metrics.selection_count > 0 else policy_diff_margin
                passed = observed >= threshold_pct
                detail = (
                    f"Observed margin {observed:.1f}% meets floor {threshold_pct:.1f}%"
                    if passed
                    else f"Observed margin {observed:.1f}% breaches margin floor {threshold_pct:.1f}%"
                )
                results.append(GuardrailResult(
                    guardrail_type=g.guardrail_type,
                    threshold_value=threshold_pct,
                    observed_value=observed,
                    passed=passed,
                    detail=detail
                ))

            elif g.guardrail_type == GuardrailType.MAX_PRICE_PAISE:
                observed = float(treatment_metrics.aov_paise)
                passed = observed <= g.threshold_value
                detail = (
                    f"Observed AOV ₹{observed/100:.2f} within ceiling ₹{g.threshold_value/100:.2f}"
                    if passed
                    else f"Observed AOV ₹{observed/100:.2f} exceeds ceiling ₹{g.threshold_value/100:.2f}"
                )
                results.append(GuardrailResult(
                    guardrail_type=g.guardrail_type,
                    threshold_value=g.threshold_value,
                    observed_value=observed,
                    passed=passed,
                    detail=detail
                ))

            elif g.guardrail_type == GuardrailType.INVENTORY_SAFETY:
                passed = treatment_metrics.guardrail_violation_count == 0
                detail = (
                    "No inventory stockout violations observed"
                    if passed
                    else f"{treatment_metrics.guardrail_violation_count} inventory safety violations observed"
                )
                results.append(GuardrailResult(
                    guardrail_type=g.guardrail_type,
                    threshold_value=0.0,
                    observed_value=float(treatment_metrics.guardrail_violation_count),
                    passed=passed,
                    detail=detail
                ))

        return results
