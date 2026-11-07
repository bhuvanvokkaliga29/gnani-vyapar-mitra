"""Unit tests for ExperimentValidator in Phase 7."""

import pytest
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentHypothesis,
    ExperimentStatus
)
from services.experiments.errors import (
    CrossTenantViolationError,
    InvalidPolicyError,
    InvalidExperimentStateError
)
from services.experiments.validator import ExperimentValidator


@pytest.fixture
def valid_experiment():
    hyp = ExperimentHypothesis(
        population_description="Target buyers",
        control_description="Baseline",
        treatment_description="Bundle",
        expected_direction="HIGHER",
        primary_metric="EXPECTED_CONTRIBUTION_PER_SHOPPER",
        rationale="Hypothesis rationale"
    )
    return PolicyExperiment(
        experiment_id="exp_val_01",
        merchant_id="merch_atlas",
        name="Atlas Test",
        population_scenarios=["scen_1", "scen_2"],
        control_policy_id="prop_ctrl",
        treatment_policy_id="prop_treat",
        control_proposal_snapshot={
            "merchant_id": "merch_atlas",
            "status": "APPROVED",
            "selected_candidate": {"candidate_id": "cand_01"}
        },
        treatment_proposal_snapshot={
            "merchant_id": "merch_atlas",
            "status": "APPROVED",
            "selected_candidate": {"candidate_id": "cand_02"}
        },
        hypothesis=hyp
    )


def test_validator_accepts_valid_experiment(valid_experiment):
    """ExperimentValidator accepts well-formed experiment."""
    ExperimentValidator.validate_preflight(valid_experiment)


def test_validator_rejects_cross_tenant_policy(valid_experiment):
    """ExperimentValidator rejects proposals belonging to different merchants."""
    valid_experiment.treatment_proposal_snapshot["merchant_id"] = "merch_other_rogue"
    with pytest.raises(CrossTenantViolationError):
        ExperimentValidator.validate_preflight(valid_experiment)


def test_validator_rejects_no_offer_policy(valid_experiment):
    """ExperimentValidator rejects experiments where either arm is NO_OFFER."""
    valid_experiment.treatment_proposal_snapshot["status"] = "NO_OFFER"
    with pytest.raises(InvalidPolicyError):
        ExperimentValidator.validate_preflight(valid_experiment)


def test_validator_rejects_empty_population(valid_experiment):
    """ExperimentValidator rejects experiments with empty population_scenarios."""
    valid_experiment.population_scenarios = []
    with pytest.raises(InvalidPolicyError):
        ExperimentValidator.validate_preflight(valid_experiment)


def test_validator_enforces_legal_state_transitions():
    """ExperimentValidator permits legal forward transitions and rejects illegal jumps."""
    # Legal transitions
    ExperimentValidator.validate_state_transition(ExperimentStatus.DRAFT, ExperimentStatus.VALIDATED)
    ExperimentValidator.validate_state_transition(ExperimentStatus.VALIDATED, ExperimentStatus.READY)
    ExperimentValidator.validate_state_transition(ExperimentStatus.READY, ExperimentStatus.RUNNING)
    ExperimentValidator.validate_state_transition(ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED)

    # Illegal jump: DRAFT -> COMPLETED
    with pytest.raises(InvalidExperimentStateError):
        ExperimentValidator.validate_state_transition(ExperimentStatus.DRAFT, ExperimentStatus.COMPLETED)

    # Terminal state cannot regress
    with pytest.raises(InvalidExperimentStateError):
        ExperimentValidator.validate_state_transition(ExperimentStatus.COMPLETED, ExperimentStatus.RUNNING)


def test_validator_enforces_immutability(valid_experiment):
    """Attempting to mutate policy snapshots while experiment is RUNNING raises error."""
    valid_experiment.status = ExperimentStatus.RUNNING

    with pytest.raises(InvalidExperimentStateError):
        ExperimentValidator.validate_immutability(
            valid_experiment,
            {"treatment_policy_id": "prop_mutated_new"}
        )
