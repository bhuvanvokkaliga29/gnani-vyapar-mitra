"""Experiment Validator: Pre-flight validation of policy experiments, tenant isolation, and immutability."""

from typing import Dict, Any, List
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentStatus,
    GuardrailType
)
from services.experiments.errors import (
    InvalidPolicyError,
    CrossTenantViolationError,
    InvalidExperimentStateError,
    GuardrailViolationError
)


class ExperimentValidator:
    """Validates policy experiment integrity, compatibility, and safety invariants."""

    @staticmethod
    def validate_preflight(experiment: PolicyExperiment) -> None:
        """Validate an experiment before it can be transitioned to READY or RUNNING."""
        # 1. Tenant Alignment
        ctrl_snapshot = experiment.control_proposal_snapshot
        treat_snapshot = experiment.treatment_proposal_snapshot

        ctrl_merchant = ctrl_snapshot.get("merchant_id")
        treat_merchant = treat_snapshot.get("merchant_id")

        if ctrl_merchant != experiment.merchant_id or treat_merchant != experiment.merchant_id:
            raise CrossTenantViolationError(
                f"Tenant mismatch: Experiment belongs to merchant '{experiment.merchant_id}', "
                f"but control is '{ctrl_merchant}' and treatment is '{treat_merchant}'."
            )

        # 2. Reject NO_OFFER policies
        ctrl_status = ctrl_snapshot.get("status")
        treat_status = treat_snapshot.get("status")

        if ctrl_status == "NO_OFFER":
            raise InvalidPolicyError("Control policy is NO_OFFER; cannot run experiment against empty baseline.")
        if treat_status == "NO_OFFER":
            raise InvalidPolicyError("Treatment policy is NO_OFFER; cannot evaluate empty treatment proposal.")

        # 3. Selected candidate presence
        ctrl_cand = ctrl_snapshot.get("selected_candidate")
        treat_cand = treat_snapshot.get("selected_candidate")
        if not ctrl_cand:
            raise InvalidPolicyError("Control policy snapshot has no selected_candidate.")
        if not treat_cand:
            raise InvalidPolicyError("Treatment policy snapshot has no selected_candidate.")

        # 4. Hypothesis completeness
        hyp = experiment.hypothesis
        if not hyp.population_description or not hyp.control_description or not hyp.treatment_description:
            raise InvalidPolicyError("Experiment hypothesis is incomplete; population, control, and treatment must be defined.")
        if not hyp.expected_direction or hyp.expected_direction not in ["HIGHER", "LOWER"]:
            raise InvalidPolicyError("Hypothesis expected_direction must be 'HIGHER' or 'LOWER'.")

        # 5. Guardrail Validity
        for g in experiment.guardrails:
            if g.guardrail_type == GuardrailType.MIN_MARGIN_PERCENT and (g.threshold_value < 0 or g.threshold_value > 1.0):
                raise GuardrailViolationError(f"MIN_MARGIN_PERCENT threshold must be between 0.0 and 1.0, got {g.threshold_value}")
            if g.guardrail_type == GuardrailType.MAX_DISCOUNT_PERCENT and (g.threshold_value < 0 or g.threshold_value > 1.0):
                raise GuardrailViolationError(f"MAX_DISCOUNT_PERCENT threshold must be between 0.0 and 1.0, got {g.threshold_value}")

        # 6. Target Population
        if not experiment.population_scenarios:
            raise InvalidPolicyError("Experiment population_scenarios must not be empty.")

    @staticmethod
    def validate_state_transition(
        current_status: ExperimentStatus,
        target_status: ExperimentStatus
    ) -> None:
        """Validate legal transitions in the experiment state machine."""
        allowed_transitions = {
            ExperimentStatus.DRAFT: [ExperimentStatus.VALIDATED, ExperimentStatus.READY, ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED],
            ExperimentStatus.VALIDATED: [ExperimentStatus.READY, ExperimentStatus.RUNNING, ExperimentStatus.DRAFT, ExperimentStatus.CANCELLED],
            ExperimentStatus.READY: [ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED],
            ExperimentStatus.RUNNING: [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED, ExperimentStatus.INCONCLUSIVE],
            ExperimentStatus.COMPLETED: [],  # Terminal
            ExperimentStatus.FAILED: [],     # Terminal
            ExperimentStatus.CANCELLED: [],  # Terminal
            ExperimentStatus.INCONCLUSIVE: [] # Terminal
        }

        if target_status not in allowed_transitions.get(current_status, []):
            raise InvalidExperimentStateError(
                f"Illegal state transition from '{current_status.value}' to '{target_status.value}'."
            )

    @staticmethod
    def validate_immutability(
        existing_experiment: PolicyExperiment,
        update_data: Dict[str, Any]
    ) -> None:
        """Ensure critical experiment configuration cannot be modified once RUNNING or COMPLETED."""
        if existing_experiment.status in [ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED]:
            immutable_fields = [
                "control_policy_id",
                "treatment_policy_id",
                "control_proposal_snapshot",
                "treatment_proposal_snapshot",
                "hypothesis",
                "primary_metric",
                "randomization_seed",
                "merchant_id"
            ]
            for field in immutable_fields:
                if field in update_data and update_data[field] != getattr(existing_experiment, field):
                    raise InvalidExperimentStateError(
                        f"Field '{field}' is immutable while experiment is {existing_experiment.status.value}."
                    )
