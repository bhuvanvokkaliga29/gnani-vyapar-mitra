"""Benchmark evaluation test suite executing all 50 golden Phase 7 experiment scenarios."""

import pytest
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentHypothesis,
    ExperimentObservation,
    VariantType,
    OutcomeType,
    ExperimentStatus
)
from services.experiments.benchmark import get_all_experiment_scenarios
from services.experiments.diff import PolicyDiffEngine
from services.experiments.assignment import AssignmentEngine
from services.experiments.metrics import ExperimentMetricEngine
from services.experiments.evaluator import ExperimentEvaluator
from services.buyer_lab.simulator import BuyerSimulator
from services.buyer_lab.schemas import BuyerOffer


@pytest.fixture
def simulator():
    return BuyerSimulator()


def test_benchmark_suite_size():
    """Verify that the experiment benchmark suite contains 50 comprehensive scenarios."""
    scenarios = get_all_experiment_scenarios()
    assert len(scenarios) == 50


@pytest.mark.parametrize("scenario", get_all_experiment_scenarios(), ids=lambda s: s.scenario_id)
def test_execute_experiment_benchmark_scenario(scenario, simulator):
    """Execute each golden experiment scenario and assert 100% compliance with expected winner and evidence status."""
    diff = PolicyDiffEngine.compute_diff(
        scenario.control_proposal,
        scenario.treatment_proposal
    )

    hyp = ExperimentHypothesis(
        population_description="Target buyers",
        control_description="Baseline policy",
        treatment_description="Alternative policy",
        expected_direction="HIGHER",
        primary_metric=scenario.primary_metric,
        rationale="Benchmark scenario hypothesis"
    )

    experiment = PolicyExperiment(
        experiment_id=scenario.scenario_id,
        merchant_id="merch_atlas_travel",
        name=scenario.name,
        population_scenarios=list(scenario.population_intents.keys()),
        control_policy_id=scenario.control_proposal["proposal_id"],
        treatment_policy_id=scenario.treatment_proposal["proposal_id"],
        control_proposal_snapshot=scenario.control_proposal,
        treatment_proposal_snapshot=scenario.treatment_proposal,
        policy_diff=diff,
        hypothesis=hyp,
        primary_metric=scenario.primary_metric,
        guardrails=scenario.guardrails,
        randomization_seed=scenario.randomization_seed
    )

    # 1. Assign population
    assignments = AssignmentEngine.assign_population(
        experiment_id=experiment.experiment_id,
        scenario_ids=experiment.population_scenarios,
        randomization_seed=experiment.randomization_seed
    )

    ctrl_obs = []
    treat_obs = []

    # 2. Simulate outcomes
    for sid, variant in assignments:
        intent = scenario.population_intents[sid]
        proposal = scenario.control_proposal if variant == VariantType.CONTROL else scenario.treatment_proposal
        cand = proposal["selected_candidate"]
        cand_econ = cand["economics"]

        merchant_offer = BuyerOffer(
            offer_id=f"off_{cand['candidate_id']}",
            merchant_id="merch_atlas_travel",
            merchant_label="Atlas Travel Gear",
            product_id=cand["product_id"],
            product_name=cand["product_name"],
            category=cand["category"],
            price_paise=cand["price_paise"],
            currency=cand["currency"],
            availability=cand["availability"],
            relevant_attributes=cand["relevant_attributes"],
            included_items=cand["included_items"],
            warranty_months=cand["warranty_months"],
            delivery_days=cand["delivery_days"],
            incentives=cand.get("incentives", [])
        )

        sim_res = simulator.simulate_selection(
            intent=intent,
            offers=[merchant_offer],
            scenario_id=sid
        )
        is_sel = (sim_res.selected_offer_id == merchant_offer.offer_id)

        rev = merchant_offer.price_paise if is_sel else 0
        contrib = (rev - cand_econ["cogs_paise"]) if is_sel else 0
        margin = float(cand_econ["margin_percent"]) if is_sel else 0.0

        obs = ExperimentObservation(
            observation_id=f"obs_{sid}_{variant.value}",
            experiment_id=experiment.experiment_id,
            scenario_id=sid,
            variant=variant,
            outcome_type=OutcomeType.SIMULATED,
            is_selected=is_sel,
            revenue_paise=rev,
            contribution_paise=contrib,
            margin_percent=margin,
            idempotency_key=f"idem_{sid}_{variant.value}"
        )
        if variant == VariantType.CONTROL:
            ctrl_obs.append(obs)
        else:
            treat_obs.append(obs)

    # 3. Aggregate metrics & deltas
    ctrl_metrics = ExperimentMetricEngine.aggregate_variant_metrics(ctrl_obs)
    treat_metrics = ExperimentMetricEngine.aggregate_variant_metrics(treat_obs)
    deltas = ExperimentMetricEngine.compute_metric_deltas(ctrl_metrics, treat_metrics)

    # 4. Evaluate guardrails
    guardrail_res = ExperimentMetricEngine.evaluate_guardrails(
        guardrails=experiment.guardrails,
        treatment_metrics=treat_metrics,
        policy_diff_margin=diff.treatment_margin_percent
    )

    # 5. Evaluate result
    result = ExperimentEvaluator.evaluate_experiment(
        experiment=experiment,
        control_metrics=ctrl_metrics,
        treatment_metrics=treat_metrics,
        metric_deltas=deltas,
        guardrail_results=guardrail_res,
        min_sample_threshold=10
    )

    # Assert Compliance with Scenario Truth
    assert result.winner == scenario.expected_winner, (
        f"Scenario {scenario.scenario_id} failed winner expectation: "
        f"expected {scenario.expected_winner}, got {result.winner}. "
        f"Rationale: {result.winner_rationale}"
    )
    assert result.evidence_status == scenario.expected_evidence_status, (
        f"Scenario {scenario.scenario_id} failed evidence status: "
        f"expected {scenario.expected_evidence_status}, got {result.evidence_status}."
    )
