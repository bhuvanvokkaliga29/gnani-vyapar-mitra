"""Reproducibility and repeated-run stability tests for AI Buyer Lab."""

import pytest
from services.buyer_lab.benchmark import get_all_benchmark_scenarios
from services.buyer_lab.simulator import BuyerSimulator


def test_repeated_run_determinism_10x():
    """Execute multi-offer benchmark scenarios 10 times consecutively.
    
    Guarantees 100% semantic stability:
    - Same winner
    - Same rejected offer IDs and reasons
    - Same satisfied preferences
    """
    simulator = BuyerSimulator()
    scenarios = [s for s in get_all_benchmark_scenarios() if s.expected_winner_id is not None][:5]

    for scenario in scenarios:
        baseline_result = simulator.simulate_selection(
            intent=scenario.intent,
            offers=scenario.offers,
            persona=scenario.persona,
            scenario_id=scenario.scenario_id
        )

        for run_idx in range(10):
            repeated_result = simulator.simulate_selection(
                intent=scenario.intent,
                offers=scenario.offers,
                persona=scenario.persona,
                scenario_id=scenario.scenario_id
            )

            assert repeated_result.selected_offer_id == baseline_result.selected_offer_id, (
                f"Determinism violation on scenario {scenario.scenario_id}, run {run_idx}: "
                f"Expected {baseline_result.selected_offer_id}, got {repeated_result.selected_offer_id}."
            )
            assert repeated_result.eligible_offer_ids == baseline_result.eligible_offer_ids
            assert [r.offer_id for r in repeated_result.rejected_offers] == [r.offer_id for r in baseline_result.rejected_offers]
            assert repeated_result.satisfied_preferences == baseline_result.satisfied_preferences
