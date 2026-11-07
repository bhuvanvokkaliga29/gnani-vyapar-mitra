"""Reproducibility and repeated-run stability tests for Phase 7 Experiments."""

import pytest
from services.experiments.benchmark import get_all_experiment_scenarios
from services.experiments.assignment import AssignmentEngine
from services.experiments.diff import PolicyDiffEngine
from services.experiments.metrics import ExperimentMetricEngine
from services.experiments.evaluator import ExperimentEvaluator
from services.experiments.schemas import PolicyExperiment, ExperimentHypothesis, ExperimentObservation, VariantType, OutcomeType
from services.buyer_lab.simulator import BuyerSimulator
from services.buyer_lab.schemas import BuyerOffer


def test_experiment_10x_repeated_run_stability():
    """Execute benchmark scenario 10 times consecutively with identical seed.
    
    Guarantees 100% semantic selection stability:
    - Same arm assignments for all scenarios
    - Same selection counts
    - Same expected contribution per shopper
    - Same winner and evidence status
    """
    simulator = BuyerSimulator()
    scenario = get_all_experiment_scenarios()[0]

    baseline_assignments = AssignmentEngine.assign_population(
        experiment_id=scenario.scenario_id,
        scenario_ids=list(scenario.population_intents.keys()),
        randomization_seed=scenario.randomization_seed
    )

    diff = PolicyDiffEngine.compute_diff(scenario.control_proposal, scenario.treatment_proposal)
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
        hypothesis=ExperimentHypothesis(
            population_description="Target",
            control_description="Ctrl",
            treatment_description="Treat",
            expected_direction="HIGHER",
            primary_metric=scenario.primary_metric,
            rationale="Rationale"
        ),
        primary_metric=scenario.primary_metric,
        guardrails=scenario.guardrails,
        randomization_seed=scenario.randomization_seed
    )

    def run_eval():
        ctrl_obs = []
        treat_obs = []
        for sid, variant in baseline_assignments:
            intent = scenario.population_intents[sid]
            cand = (scenario.control_proposal if variant == VariantType.CONTROL else scenario.treatment_proposal)["selected_candidate"]
            offer = BuyerOffer(
                offer_id=f"off_{cand['candidate_id']}",
                merchant_id="merch_atlas_travel",
                merchant_label="Atlas",
                product_id=cand["product_id"],
                product_name=cand["product_name"],
                price_paise=cand["price_paise"],
                warranty_months=cand["warranty_months"],
                relevant_attributes=cand["relevant_attributes"],
                included_items=cand["included_items"]
            )
            sim_res = simulator.simulate_selection(intent, [offer], scenario_id=sid)
            is_sel = (sim_res.selected_offer_id == offer.offer_id)
            rev = offer.price_paise if is_sel else 0
            contrib = (rev - cand["economics"]["cogs_paise"]) if is_sel else 0

            obs = ExperimentObservation(
                observation_id=f"obs_{sid}",
                experiment_id=experiment.experiment_id,
                scenario_id=sid,
                variant=variant,
                is_selected=is_sel,
                revenue_paise=rev,
                contribution_paise=contrib,
                margin_percent=float(cand["economics"]["margin_percent"]),
                idempotency_key=f"idem_{sid}"
            )
            (ctrl_obs if variant == VariantType.CONTROL else treat_obs).append(obs)

        c_met = ExperimentMetricEngine.aggregate_variant_metrics(ctrl_obs)
        t_met = ExperimentMetricEngine.aggregate_variant_metrics(treat_obs)
        deltas = ExperimentMetricEngine.compute_metric_deltas(c_met, t_met)
        g_res = ExperimentMetricEngine.evaluate_guardrails(experiment.guardrails, t_met)
        return ExperimentEvaluator.evaluate_experiment(experiment, c_met, t_met, deltas, g_res)

    baseline_result = run_eval()

    # Repeat 10 times
    for run_idx in range(10):
        # Verify assignment stability
        repeated_assignments = AssignmentEngine.assign_population(
            experiment_id=scenario.scenario_id,
            scenario_ids=list(scenario.population_intents.keys()),
            randomization_seed=scenario.randomization_seed
        )
        assert repeated_assignments == baseline_assignments, f"Assignment instability on run {run_idx}"

        repeated_result = run_eval()
        assert repeated_result.winner == baseline_result.winner
        assert repeated_result.evidence_status == baseline_result.evidence_status
        assert repeated_result.control_metrics.selection_count == baseline_result.control_metrics.selection_count
        assert repeated_result.treatment_metrics.selection_count == baseline_result.treatment_metrics.selection_count
        assert repeated_result.treatment_metrics.expected_contribution_per_shopper_paise == baseline_result.treatment_metrics.expected_contribution_per_shopper_paise
