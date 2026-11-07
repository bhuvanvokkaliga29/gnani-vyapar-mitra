"""Unit tests for AssignmentEngine in Phase 7."""

import pytest
from services.experiments.schemas import VariantType
from services.experiments.assignment import AssignmentEngine


def test_assignment_reproducibility():
    """Identical (experiment_id, scenario_id, seed) produces identical variant every time."""
    exp_id = "exp_repro_test"
    scenario_id = "scen_buyer_01"
    seed = 42

    v1 = AssignmentEngine.assign_variant(exp_id, scenario_id, seed)
    v2 = AssignmentEngine.assign_variant(exp_id, scenario_id, seed)
    v3 = AssignmentEngine.assign_variant(exp_id, scenario_id, seed)

    assert v1 == v2 == v3


def test_seed_changes_assignment_distribution():
    """Varying the seed produces different hash sequences across a scenario population."""
    exp_id = "exp_seed_test"
    scenarios = [f"scen_{i}" for i in range(20)]

    assignments_seed42 = AssignmentEngine.assign_population(exp_id, scenarios, randomization_seed=42)
    assignments_seed99 = AssignmentEngine.assign_population(exp_id, scenarios, randomization_seed=999)

    # They should not be identical lists
    assert assignments_seed42 != assignments_seed99


def test_population_assignment_has_both_arms():
    """A realistic population of 20 scenarios assigns scenarios to both CONTROL and TREATMENT."""
    exp_id = "exp_population_test"
    scenarios = [f"scen_{i}" for i in range(20)]

    assignments = AssignmentEngine.assign_population(exp_id, scenarios, randomization_seed=42)
    variants = [v for _, v in assignments]

    assert VariantType.CONTROL in variants
    assert VariantType.TREATMENT in variants
