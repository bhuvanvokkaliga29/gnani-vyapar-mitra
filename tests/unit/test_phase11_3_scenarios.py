"""Unit Tests for Phase 11.3 Economic Benchmark Scenarios.

Validates:
1. All 11 economic scenarios conform to benchmark-scenario/v1 schema.
2. All 11 scenarios are registered in BenchmarkRegistry under ScenarioCategory.ECONOMICS.
3. Every scenario has explicit merchant initial state, buyer context, and non-empty expectations.
4. Categorization, tags, and failure class coverage across all 11 scenarios.
5. Invariant and no-side-effect expectation structure.
6. Information hygiene: zero leakage of raw secrets or sensitive tokens in scenario specs.
"""

import pytest
from services.benchmark.schemas import (
    BENCHMARK_SCENARIO_VERSION,
    BenchmarkScenario,
    ScenarioCategory,
    FailureClass,
    ExpectationType,
)
from services.benchmark.registry import BenchmarkRegistry
from services.benchmark.economic_scenarios import (
    ECONOMIC_SCENARIOS,
    SCENARIO_ECON_ZERO_CONTRIBUTION,
    SCENARIO_ECON_NEGATIVE_CONTRIBUTION,
    SCENARIO_ECON_REVENUE_NOT_EQUAL_CONTRIBUTION,
    SCENARIO_ECON_BUNDLE_MULTI_ITEM_MATH,
    SCENARIO_ECON_MULTI_UNIT_QUANTITY,
    SCENARIO_ECON_INVENTORY_BARRIER,
    SCENARIO_ECON_NO_OFFER_BASELINE,
    SCENARIO_ECON_EXPECTED_VS_OBSERVED,
    SCENARIO_ECON_REJECTION_ZERO_SIDE_EFFECTS,
    SCENARIO_ECON_PROMOTION_GATING,
    SCENARIO_ECON_CROSS_MERCHANT_ISOLATION,
)


def test_economic_suite_count_and_identity():
    """Verify exactly 11 distinct economic scenarios in suite."""
    assert len(ECONOMIC_SCENARIOS) == 11
    scenario_ids = [s.scenario_id for s in ECONOMIC_SCENARIOS]
    assert len(set(scenario_ids)) == 11, "Scenario IDs must be unique"

    expected_ids = [
        "ECON_ZERO_CONTRIBUTION_PURCHASE",
        "ECON_NEGATIVE_CONTRIBUTION_PRESERVED",
        "ECON_REVENUE_NOT_EQUAL_CONTRIBUTION",
        "ECON_BUNDLE_MULTI_ITEM_MATH",
        "ECON_MULTI_UNIT_QUANTITY_SCALING",
        "ECON_INVENTORY_SAFETY_BARRIER",
        "ECON_NO_OFFER_EQUAL_BASELINE",
        "ECON_EXPECTED_VS_OBSERVED_DIVERGENCE",
        "ECON_REJECTION_ZERO_SIDE_EFFECTS",
        "ECON_PROMOTION_ECONOMIC_GATE",
        "ECON_CROSS_MERCHANT_ECONOMIC_ISOLATION",
    ]
    for eid in expected_ids:
        assert eid in scenario_ids, f"Expected {eid} in economic scenarios"


def test_economic_registry_registration():
    """Verify all 11 economic scenarios are registered in BenchmarkRegistry."""
    econ_registered = BenchmarkRegistry.list_by_category(ScenarioCategory.ECONOMICS)
    registered_ids = {s.scenario_id for s in econ_registered}
    for scen in ECONOMIC_SCENARIOS:
        assert scen.scenario_id in registered_ids
        retrieved = BenchmarkRegistry.get(scen.scenario_id)
        assert retrieved is not None
        assert retrieved.scenario_id == scen.scenario_id


def test_economic_scenarios_schema_conformance():
    """Verify each scenario adheres to benchmark-scenario/v1 schema contracts."""
    for scen in ECONOMIC_SCENARIOS:
        assert scen.scenario_version == BENCHMARK_SCENARIO_VERSION
        assert scen.category == ScenarioCategory.ECONOMICS
        assert scen.merchant_id.startswith("merch_")
        assert scen.buyer_context is not None
        assert scen.initial_state is not None
        assert scen.initial_state.merchant is not None
        assert len(scen.expected_invariants) > 0, f"{scen.scenario_id} must have expectations"


def test_economic_scenarios_expectation_diversity():
    """Verify expectation types and failure classes are used across the suite."""
    all_exp_types = set()
    all_fail_classes = set()
    for scen in ECONOMIC_SCENARIOS:
        for exp in scen.expected_invariants:
            all_exp_types.add(exp.expectation_type)
            all_fail_classes.add(exp.failure_class)

    assert ExpectationType.EXACT_STATE in all_exp_types
    assert ExpectationType.EXACT_VALUE in all_exp_types
    assert ExpectationType.INVARIANT in all_exp_types
    assert ExpectationType.RELATIONAL in all_exp_types
    assert ExpectationType.NO_SIDE_EFFECT in all_exp_types
    assert ExpectationType.ISOLATION in all_exp_types

    assert FailureClass.ECONOMIC_INTEGRITY_FAILURE in all_fail_classes
    assert FailureClass.BUSINESS_INVARIANT_FAILURE in all_fail_classes
    assert FailureClass.SAFETY_FAILURE in all_fail_classes
    assert FailureClass.TENANT_ISOLATION_FAILURE in all_fail_classes


def test_information_hygiene_in_economic_scenarios():
    """Verify zero leakage of sensitive credentials or private tokens in specs."""
    for scen in ECONOMIC_SCENARIOS:
        dump = scen.model_dump()
        dump_str = str(dump).lower()
        assert "rzp_live_" not in dump_str
        assert "secret" not in dump_str
        assert "password" not in dump_str
        assert "api_key" not in dump_str
