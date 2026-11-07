"""Experiment Evaluator: Determines evidence status, guardrail compliance, and honest winner selection."""

from datetime import datetime, timezone
from typing import Optional, List, Dict
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentResult,
    VariantMetrics,
    MetricDelta,
    GuardrailResult,
    VariantType,
    EvidenceStatus,
    ExperimentStatus
)


class ExperimentEvaluator:
    """Evaluates experiment outcomes without manufactured statistical certainty."""

    @staticmethod
    def evaluate_experiment(
        experiment: PolicyExperiment,
        control_metrics: VariantMetrics,
        treatment_metrics: VariantMetrics,
        metric_deltas: Dict[str, MetricDelta],
        guardrail_results: List[GuardrailResult],
        min_sample_threshold: int = 10
    ) -> ExperimentResult:
        """Evaluate experiment arms and synthesize an auditable, machine-readable ExperimentResult."""
        total_samples = control_metrics.sample_size + treatment_metrics.sample_size
        primary_metric_name = experiment.primary_metric
        primary_delta = metric_deltas.get(primary_metric_name)

        actual_control_count = control_metrics.sample_size
        actual_treatment_count = treatment_metrics.sample_size
        allocation_ratio = round(actual_treatment_count / actual_control_count, 3) if actual_control_count > 0 else 0.0

        # 1. Check for Insufficient Sample
        if total_samples < min_sample_threshold or control_metrics.sample_size == 0 or treatment_metrics.sample_size == 0:
            return ExperimentResult(
                result_version="experiment-result/v1",
                experiment_id=experiment.experiment_id,
                merchant_id=experiment.merchant_id,
                status=ExperimentStatus.INCONCLUSIVE,
                evidence_status=EvidenceStatus.INSUFFICIENT_SAMPLE,
                winner=None,
                winner_rationale=(
                    f"Sample size of {total_samples} (Control: {control_metrics.sample_size}, "
                    f"Treatment: {treatment_metrics.sample_size}) is below minimum threshold of {min_sample_threshold}. "
                    "Insufficient sample size to establish a statistically reliable difference."
                ),
                sample_counts={"CONTROL": control_metrics.sample_size, "TREATMENT": treatment_metrics.sample_size},
                actual_control_count=actual_control_count,
                actual_treatment_count=actual_treatment_count,
                allocation_ratio=allocation_ratio,
                control_metrics=control_metrics,
                treatment_metrics=treatment_metrics,
                metric_deltas=metric_deltas,
                guardrail_results=guardrail_results,
                policy_diff=experiment.policy_diff,
                generated_at=datetime.now(timezone.utc)
            )

        # 2. Check Guardrail Failures
        failed_guardrails = [g for g in guardrail_results if not g.passed]
        if failed_guardrails:
            failure_details = "; ".join(g.detail for g in failed_guardrails)
            return ExperimentResult(
                result_version="experiment-result/v1",
                experiment_id=experiment.experiment_id,
                merchant_id=experiment.merchant_id,
                status=ExperimentStatus.COMPLETED,
                evidence_status=EvidenceStatus.GUARDRAIL_FAILURE,
                winner=VariantType.CONTROL,
                winner_rationale=(
                    f"Treatment variant breached experiment guardrail(s): {failure_details}. "
                    "Despite any directional selection or revenue gains, guardrail violation disqualifies Treatment. "
                    "Control policy is retained as the safe baseline."
                ),
                sample_counts={"CONTROL": control_metrics.sample_size, "TREATMENT": treatment_metrics.sample_size},
                actual_control_count=actual_control_count,
                actual_treatment_count=actual_treatment_count,
                allocation_ratio=allocation_ratio,
                control_metrics=control_metrics,
                treatment_metrics=treatment_metrics,
                metric_deltas=metric_deltas,
                guardrail_results=guardrail_results,
                policy_diff=experiment.policy_diff,
                generated_at=datetime.now(timezone.utc)
            )

        # 3. Evaluate Primary Metric (Zero Delta Check)
        if not primary_delta or primary_delta.absolute_difference == 0:
            return ExperimentResult(
                result_version="experiment-result/v1",
                experiment_id=experiment.experiment_id,
                merchant_id=experiment.merchant_id,
                status=ExperimentStatus.COMPLETED,
                evidence_status=EvidenceStatus.INCONCLUSIVE,
                winner=None,
                winner_rationale=(
                    f"No observable difference in primary metric '{primary_metric_name}' "
                    f"(Control: {primary_delta.control_value if primary_delta else 0}, "
                    f"Treatment: {primary_delta.treatment_value if primary_delta else 0}). Result is inconclusive."
                ),
                sample_counts={"CONTROL": control_metrics.sample_size, "TREATMENT": treatment_metrics.sample_size},
                actual_control_count=actual_control_count,
                actual_treatment_count=actual_treatment_count,
                allocation_ratio=allocation_ratio,
                control_metrics=control_metrics,
                treatment_metrics=treatment_metrics,
                metric_deltas=metric_deltas,
                guardrail_results=guardrail_results,
                policy_diff=experiment.policy_diff,
                generated_at=datetime.now(timezone.utc)
            )

        # 4. Effect Size & Uncertainty Threshold (Minimum Detectable Effect)
        mde_pct = getattr(experiment, "min_detectable_effect", 0.02) * 100.0
        rel_diff = abs(primary_delta.relative_difference_percent) if primary_delta.relative_difference_percent is not None else None

        if rel_diff is not None and rel_diff < mde_pct:
            return ExperimentResult(
                result_version="experiment-result/v1",
                experiment_id=experiment.experiment_id,
                merchant_id=experiment.merchant_id,
                status=ExperimentStatus.COMPLETED,
                evidence_status=EvidenceStatus.INCONCLUSIVE,
                winner=None,
                winner_rationale=(
                    f"Observed relative difference of {rel_diff:.2f}% in primary metric '{primary_metric_name}' "
                    f"(Control: {primary_delta.control_value}, Treatment: {primary_delta.treatment_value}) "
                    f"is within the uncertainty / minimum detectable effect threshold ({mde_pct:.1f}%). "
                    "The result is statistically inconclusive."
                ),
                sample_counts={"CONTROL": control_metrics.sample_size, "TREATMENT": treatment_metrics.sample_size},
                actual_control_count=actual_control_count,
                actual_treatment_count=actual_treatment_count,
                allocation_ratio=allocation_ratio,
                control_metrics=control_metrics,
                treatment_metrics=treatment_metrics,
                metric_deltas=metric_deltas,
                guardrail_results=guardrail_results,
                policy_diff=experiment.policy_diff,
                generated_at=datetime.now(timezone.utc)
            )

        # 5. Decisive Winner Selection
        if primary_delta.directionally_improved:
            winner = VariantType.TREATMENT
            rel_str = f" (+{primary_delta.relative_difference_percent:.1f}%)" if primary_delta.relative_difference_percent is not None else ""
            rationale = (
                f"Treatment demonstrated superior {primary_metric_name}{rel_str} "
                f"while satisfying all {len(guardrail_results)} experiment guardrails. "
                "Controlled difference observed across target population."
            )
        else:
            winner = VariantType.CONTROL
            rel_str = f" ({primary_delta.relative_difference_percent:.1f}%)" if primary_delta.relative_difference_percent is not None else ""
            rationale = (
                f"Control policy outperformed Treatment on {primary_metric_name}{rel_str}. "
                "Baseline policy retained."
            )

        return ExperimentResult(
            result_version="experiment-result/v1",
            experiment_id=experiment.experiment_id,
            merchant_id=experiment.merchant_id,
            status=ExperimentStatus.COMPLETED,
            evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE,
            winner=winner,
            winner_rationale=rationale,
            sample_counts={"CONTROL": control_metrics.sample_size, "TREATMENT": treatment_metrics.sample_size},
            actual_control_count=actual_control_count,
            actual_treatment_count=actual_treatment_count,
            allocation_ratio=allocation_ratio,
            control_metrics=control_metrics,
            treatment_metrics=treatment_metrics,
            metric_deltas=metric_deltas,
            guardrail_results=guardrail_results,
            policy_diff=experiment.policy_diff,
            generated_at=datetime.now(timezone.utc)
        )
