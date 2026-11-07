"""Unit Tests for Phase 11.2 Golden Adversarial Scenarios.

Validates:
1. All 10 golden scenarios exist and conform to benchmark-scenario/v1 schema.
2. All 10 scenarios are registered in BenchmarkRegistry with tag 'GOLDEN_E2E_ADVERSARIAL'.
3. Every scenario has explicit initial state, buyer context, and non-empty expectations.
4. Categorization and failure class coverage across all 10 scenarios.
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
from services.benchmark.golden_scenarios import (
    GOLDEN_SCENARIO_SUITE,
    SCENARIO_1_PAYMENT_FAILURE_TRUTH,
    SCENARIO_2_NO_OFFER_SHORT_CIRCUIT,
    SCENARIO_3_SAFETY_REJECTION_BLOCK,
    SCENARIO_4_STALE_STATE_REJECTION,
    SCENARIO_5_DUPLICATE_OUTCOME_ONCE,
    SCENARIO_6_LUCKY_PURCHASE_GATE,
    SCENARIO_7_LEARNING_NO_PROMOTION,
    SCENARIO_8_MERCHANT_BOUNDARY_ATTACK,
    SCENARIO_9_NEGATIVE_CONTRIBUTION,
    SCENARIO_10_EXECUTION_FAILURE_SHIELD,
)


def test_golden_suite_count_and_identity():
    """Verify exactly 10 distinct golden scenarios in suite."""
    assert len(GOLDEN_SCENARIO_SUITE) == 10
    scenario_ids = [s.scenario_id for s in GOLDEN_SCENARIO_SUITE]
    assert len(set(scenario_ids)) == 10, "Scenario IDs must be unique"
    
    expected_ids = [
        "GOLDEN_PAYMENT_FAILURE_TRUTH",
        "GOLDEN_NO_OFFER_SHORT_CIRCUIT",
        "GOLDEN_SAFETY_REJECTION_BLOCK",
        "GOLDEN_STALE_STATE_REJECTION",
        "GOLDEN_DUPLICATE_OUTCOME_ONCE",
        "GOLDEN_LUCKY_PURCHASE_GATE",
        "GOLDEN_LEARNING_NO_PROMOTION",
        "GOLDEN_MERCHANT_BOUNDARY_ATTACK",
        "GOLDEN_NEGATIVE_CONTRIBUTION",
        "GOLDEN_EXECUTION_FAILURE_SHIELD",
    ]
    for eid in expected_ids:
        assert eid in scenario_ids, f"Expected {eid} in golden scenarios"


def test_golden_registry_registration():
    """Verify all 10 golden scenarios are registered in BenchmarkRegistry."""
    golden_tagged = BenchmarkRegistry.list_by_tag("GOLDEN_E2E_ADVERSARIAL")
    golden_tagged_ids = [s.scenario_id for s in golden_tagged]
    
    for s in GOLDEN_SCENARIO_SUITE:
        retrieved = BenchmarkRegistry.get(s.scenario_id)
        assert retrieved is not None, f"Scenario {s.scenario_id} not found in registry"
        assert retrieved.scenario_id == s.scenario_id
        assert "GOLDEN_E2E_ADVERSARIAL" in retrieved.tags
        assert s.scenario_id in golden_tagged_ids


def test_golden_scenarios_schema_conformance():
    """Verify every golden scenario complies strictly with benchmark-scenario/v1."""
    for s in GOLDEN_SCENARIO_SUITE:
        assert s.scenario_version == BENCHMARK_SCENARIO_VERSION
        assert s.scenario_id.startswith("GOLDEN_")
        assert len(s.description) > 0
        assert s.category in ScenarioCategory
        assert s.initial_state is not None
        assert s.initial_state.merchant is not None
        assert s.initial_state.merchant.merchant_id.startswith("merch_")
        assert len(s.initial_state.products) >= 1
        assert s.buyer_context is not None
        assert s.buyer_context.raw_prompt is not None or s.buyer_context.buyer_intent is not None
        assert len(s.expected_invariants) >= 2, f"{s.scenario_id} must have at least 2 assertions"
        assert s.seed is not None


def test_golden_scenarios_coverage_categories():
    """Verify that golden scenarios cover diverse scenario categories."""
    categories = {s.category for s in GOLDEN_SCENARIO_SUITE}
    
    expected_categories = {
        ScenarioCategory.OUTCOME,
        ScenarioCategory.EXECUTION,
        ScenarioCategory.SAFETY,
        ScenarioCategory.RESILIENCE,
        ScenarioCategory.LIFECYCLE,
        ScenarioCategory.LEARNING,
        ScenarioCategory.TENANT,
        ScenarioCategory.ECONOMICS,
        ScenarioCategory.DECISION,
    }
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"


def test_golden_scenarios_failure_class_coverage():
    """Verify that expectations span all major failure classes."""
    failure_classes = set()
    for s in GOLDEN_SCENARIO_SUITE:
        for exp in s.expected_invariants:
            failure_classes.add(exp.failure_class)
            
    expected_fclasses = {
        FailureClass.SAFETY_FAILURE,
        FailureClass.LIFECYCLE_FAILURE,
        FailureClass.BUSINESS_INVARIANT_FAILURE,
        FailureClass.ECONOMIC_INTEGRITY_FAILURE,
        FailureClass.TENANT_ISOLATION_FAILURE,
        FailureClass.LEARNING_INTEGRITY_FAILURE,
        FailureClass.EXPECTED_STATE_MISMATCH,
    }
    assert expected_fclasses.issubset(failure_classes), f"Missing failure classes: {expected_fclasses - failure_classes}"


def test_golden_scenarios_expectation_types():
    """Verify golden scenarios test both positive invariants and negative side effects."""
    types = set()
    for s in GOLDEN_SCENARIO_SUITE:
        for exp in s.expected_invariants:
            types.add(exp.expectation_type)
            
    assert ExpectationType.INVARIANT in types
    assert ExpectationType.NO_SIDE_EFFECT in types
    assert ExpectationType.EXACT_STATE in types


def test_golden_scenarios_information_hygiene():
    """Verify scenario specs contain zero leaked raw credentials or tokens."""
    sensitive_keys = ["key_secret", "cogs_paise", "bearer", "password", "sk_live", "rzp_live"]
    for s in GOLDEN_SCENARIO_SUITE:
        serialized = s.model_dump_json().lower()
        for sen in sensitive_keys:
            assert sen not in serialized, f"Sensitive term '{sen}' found in {s.scenario_id}"
