"""Benchmark evaluation test suite executing all 50 golden AI Buyer Lab scenarios."""

import pytest
from services.buyer_lab.benchmark import get_all_benchmark_scenarios
from services.buyer_lab.simulator import BuyerSimulator
from services.buyer_lab.schemas import SelectionTaxonomy, OfferRejectionCode


@pytest.fixture
def simulator():
    return BuyerSimulator()


def test_benchmark_suite_size():
    """Verify that the benchmark suite contains 50 comprehensive scenarios."""
    scenarios = get_all_benchmark_scenarios()
    assert len(scenarios) == 50


@pytest.mark.parametrize("scenario", get_all_benchmark_scenarios(), ids=lambda s: s.scenario_id)
def test_execute_benchmark_scenario(scenario, simulator):
    """Execute each golden scenario and assert 100% decision and rejection correctness."""
    result = simulator.simulate_selection(
        intent=scenario.intent,
        offers=scenario.offers,
        persona=scenario.persona,
        scenario_id=scenario.scenario_id
    )

    # 1. Assert Winner Correctness
    assert result.selected_offer_id == scenario.expected_winner_id, (
        f"Scenario {scenario.scenario_id} failed: "
        f"Expected winner {scenario.expected_winner_id}, got {result.selected_offer_id}. "
        f"Rationale: {result.selection_rationale}"
    )

    # 2. If winner is None, verify NO_ELIGIBLE_OFFER taxonomy
    if scenario.expected_winner_id is None:
        assert SelectionTaxonomy.NO_ELIGIBLE_OFFER in result.selection_reasons
        assert len(result.eligible_offer_ids) == 0

    # 3. Assert Expected Rejections
    observed_rejections = {
        r.offer_id: r.rejection_reason for r in result.rejected_offers
    }
    for expected_offer_id, expected_code in scenario.expected_rejections.items():
        assert expected_offer_id in observed_rejections, (
            f"Scenario {scenario.scenario_id}: Expected {expected_offer_id} to be rejected, but it was not."
        )
        assert observed_rejections[expected_offer_id] == expected_code, (
            f"Scenario {scenario.scenario_id}: Expected rejection code {expected_code} for {expected_offer_id}, "
            f"got {observed_rejections[expected_offer_id]}."
        )

    # 4. Invariant: If a winner was selected, it CANNOT be in rejected_offers
    if result.selected_offer_id:
        assert result.selected_offer_id not in observed_rejections
        assert result.selected_offer_id in result.eligible_offer_ids
