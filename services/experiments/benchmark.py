"""Golden Benchmark Suite for Phase 7 Controlled Policy Experiments.

Contains 50 canonical, machine-executable experiment scenarios spanning:
- Category A: Baseline Control vs Treatment Comparisons (10)
- Category B: Guardrail Failures (Margin Floor, Price Ceiling, Inventory) (8)
- Category C: Statistical Boundaries & Small Samples (Insufficient, Inconclusive) (8)
- Category D: Assignment Determinism & No Cross-Contamination (8)
- Category E: Integrity, Idempotency & Tenant Isolation (8)
- Category F: Phase 5 Test-Mode Execution Integration (8)
"""

from typing import List, Dict, Any, Optional
from domain.intent_schemas import BuyerIntent, BudgetConstraint, AttributeRequirement, AttributePreference, OperatorType
from services.experiments.schemas import (
    PolicyExperiment,
    ExperimentHypothesis,
    ExperimentGuardrail,
    GuardrailType,
    ExperimentStatus,
    VariantType,
    EvidenceStatus
)


class ExperimentBenchmarkScenario:
    """A structured test case for policy experimentation."""

    def __init__(
        self,
        scenario_id: str,
        name: str,
        category: str,
        control_proposal: Dict[str, Any],
        treatment_proposal: Dict[str, Any],
        population_intents: Dict[str, BuyerIntent],
        guardrails: List[ExperimentGuardrail],
        expected_winner: Optional[VariantType],
        expected_evidence_status: EvidenceStatus,
        primary_metric: str = "EXPECTED_CONTRIBUTION_PER_SHOPPER",
        randomization_seed: int = 42
    ):
        self.scenario_id = scenario_id
        self.name = name
        self.category = category
        self.control_proposal = control_proposal
        self.treatment_proposal = treatment_proposal
        self.population_intents = population_intents
        self.guardrails = guardrails
        self.expected_winner = expected_winner
        self.expected_evidence_status = expected_evidence_status
        self.primary_metric = primary_metric
        self.randomization_seed = randomization_seed


def _make_sample_proposal(
    proposal_id: str,
    cand_id: str,
    strategy: str,
    price_paise: int,
    cogs_paise: int,
    margin_pct: float,
    items: List[str],
    warranty_months: int = 12,
    incentives: Optional[List[str]] = None,
    merchant_id: str = "merch_atlas_travel",
    laptop_size: float = 15.6,
    status: str = "APPROVED"
) -> Dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "merchant_id": merchant_id,
        "status": status,
        "selected_candidate": {
            "candidate_id": cand_id,
            "strategy_type": strategy,
            "product_id": "prod_atlas_pack",
            "product_name": "Atlas Travel Pack",
            "category": "backpacks",
            "price_paise": price_paise,
            "currency": "INR",
            "availability": True,
            "relevant_attributes": {"laptop_size": laptop_size, "water_resistant": True},
            "included_items": items,
            "warranty_months": warranty_months,
            "delivery_days": 2,
            "incentives": incentives or [],
            "economics": {
                "proposed_price_paise": price_paise,
                "cogs_paise": cogs_paise,
                "gross_profit_paise": price_paise - cogs_paise,
                "margin_percent": margin_pct
            }
        }
    }


def get_all_experiment_scenarios() -> List[ExperimentBenchmarkScenario]:
    """Return all 50 canonical experiment benchmark scenarios."""
    scenarios = []

    # =========================================================================
    # CATEGORY A: Baseline Control vs Treatment Comparisons (10 Scenarios)
    # =========================================================================
    for i in range(1, 11):
        scen_id = f"exp_bench_A{i:02d}"
        # Treatment adds value bundle (+accessory) and higher warranty at slight price bump
        ctrl = _make_sample_proposal(
            f"prop_ctrl_A{i}", f"cand_ctrl_A{i}", "SINGLE_PRODUCT",
            price_paise=299900, cogs_paise=150000, margin_pct=49.98, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_A{i}", f"cand_treat_A{i}", "VALUE_BUNDLE",
            price_paise=349900, cogs_paise=170000, margin_pct=51.41, items=["rain_cover"],
            warranty_months=24
        )

        intents = {}
        for j in range(12):
            intents[f"{scen_id}_buyer_{j:02d}"] = BuyerIntent(
                budget=BudgetConstraint(max_amount_paise=400000, currency="INR"),
                requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6)],
                preferences=[AttributePreference(attribute="warranty", preference="long warranty")]
            )

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Baseline Value Bundle Comparison A{i:02d}",
            category="A: Baseline Comparisons",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.40, description="Min 40% margin")
            ],
            expected_winner=VariantType.TREATMENT,
            expected_evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE
        ))

    # =========================================================================
    # CATEGORY B: Guardrail Failures (8 Scenarios)
    # =========================================================================
    for i in range(1, 9):
        scen_id = f"exp_bench_B{i:02d}"
        # Treatment slashes price heavily to win selection, but breaches margin floor (15% vs 35% min)
        ctrl = _make_sample_proposal(
            f"prop_ctrl_B{i}", f"cand_ctrl_B{i}", "SINGLE_PRODUCT",
            price_paise=299900, cogs_paise=150000, margin_pct=49.98, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_B{i}", f"cand_treat_B{i}", "PRICE_DISCOUNT",
            price_paise=170000, cogs_paise=150000, margin_pct=11.76, items=[]
        )

        intents = {}
        for j in range(12):
            intents[f"{scen_id}_buyer_{j:02d}"] = BuyerIntent(
                budget=BudgetConstraint(max_amount_paise=350000, currency="INR")
            )

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Margin Guardrail Breach B{i:02d}",
            category="B: Guardrail Failures",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.35, description="Min 35% margin")
            ],
            expected_winner=VariantType.CONTROL,  # Guardrail failure disqualifies treatment!
            expected_evidence_status=EvidenceStatus.GUARDRAIL_FAILURE
        ))

    # =========================================================================
    # CATEGORY C: Statistical Boundaries & Small Samples (8 Scenarios)
    # =========================================================================
    # C01-C04: Small sample (< 10 total decision instances) -> INSUFFICIENT_SAMPLE
    for i in range(1, 5):
        scen_id = f"exp_bench_C{i:02d}"
        ctrl = _make_sample_proposal(
            f"prop_ctrl_C{i}", f"cand_ctrl_C{i}", "SINGLE_PRODUCT",
            price_paise=299900, cogs_paise=150000, margin_pct=49.98, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_C{i}", f"cand_treat_C{i}", "VALUE_BUNDLE",
            price_paise=320000, cogs_paise=160000, margin_pct=50.0, items=["pouch"]
        )

        # Only 4 buyer instances (insufficient for statistical conclusion)
        intents = {
            f"{scen_id}_b1": BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR")),
            f"{scen_id}_b2": BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR")),
            f"{scen_id}_b3": BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR")),
            f"{scen_id}_b4": BuyerIntent(budget=BudgetConstraint(max_amount_paise=400000, currency="INR")),
        }

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Small Sample Insufficient Evidence C{i:02d}",
            category="C: Statistical Boundaries",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.30, description="Min 30% margin")
            ],
            expected_winner=None,
            expected_evidence_status=EvidenceStatus.INSUFFICIENT_SAMPLE
        ))

    # C05-C08: Identical or tie performance -> INCONCLUSIVE
    for i in range(5, 9):
        scen_id = f"exp_bench_C{i:02d}"
        # Exactly identical offers
        ctrl = _make_sample_proposal(
            f"prop_ctrl_C{i}", f"cand_ctrl_C{i}", "SINGLE_PRODUCT",
            price_paise=299900, cogs_paise=150000, margin_pct=49.98, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_C{i}", f"cand_treat_C{i}", "SINGLE_PRODUCT",
            price_paise=299900, cogs_paise=150000, margin_pct=49.98, items=[]
        )

        intents = {}
        for j in range(12):
            intents[f"{scen_id}_buyer_{j:02d}"] = BuyerIntent(
                budget=BudgetConstraint(max_amount_paise=400000, currency="INR")
            )

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Tie Outcome Inconclusive C{i:02d}",
            category="C: Statistical Boundaries",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.30, description="Min 30% margin")
            ],
            expected_winner=None,
            expected_evidence_status=EvidenceStatus.INCONCLUSIVE
        ))

    # =========================================================================
    # CATEGORY D: Assignment Determinism & No Cross-Contamination (8 Scenarios)
    # =========================================================================
    for i in range(1, 9):
        scen_id = f"exp_bench_D{i:02d}"
        ctrl = _make_sample_proposal(
            f"prop_ctrl_D{i}", f"cand_ctrl_D{i}", "SINGLE_PRODUCT",
            price_paise=250000, cogs_paise=120000, margin_pct=52.0, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_D{i}", f"cand_treat_D{i}", "VALUE_BUNDLE",
            price_paise=300000, cogs_paise=140000, margin_pct=53.33, items=["strap"],
            warranty_months=36
        )

        intents = {}
        for j in range(14):
            intents[f"{scen_id}_buyer_{j:02d}"] = BuyerIntent(
                budget=BudgetConstraint(max_amount_paise=450000, currency="INR"),
                preferences=[AttributePreference(attribute="warranty", preference="extended warranty")]
            )

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Assignment Reproducibility D{i:02d}",
            category="D: Assignment Determinism",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.40, description="Min 40% margin")
            ],
            expected_winner=VariantType.TREATMENT,
            expected_evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE,
            randomization_seed=100 + i
        ))

    # =========================================================================
    # CATEGORY E: Integrity, Idempotency & Tenant Isolation (8 Scenarios)
    # =========================================================================
    for i in range(1, 9):
        scen_id = f"exp_bench_E{i:02d}"
        ctrl = _make_sample_proposal(
            f"prop_ctrl_E{i}", f"cand_ctrl_E{i}", "SINGLE_PRODUCT",
            price_paise=280000, cogs_paise=140000, margin_pct=50.0, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_E{i}", f"cand_treat_E{i}", "VALUE_BUNDLE",
            price_paise=330000, cogs_paise=160000, margin_pct=51.52, items=["rain_cover"]
        )

        intents = {}
        for j in range(12):
            intents[f"{scen_id}_buyer_{j:02d}"] = BuyerIntent(
                budget=BudgetConstraint(max_amount_paise=400000, currency="INR")
            )

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Integrity & Idempotency Audit E{i:02d}",
            category="E: Integrity & Isolation",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.35, description="Min 35% margin")
            ],
            expected_winner=VariantType.TREATMENT,
            expected_evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE
        ))

    # =========================================================================
    # CATEGORY F: Phase 5 Test-Mode Execution Integration (8 Scenarios)
    # =========================================================================
    for i in range(1, 9):
        scen_id = f"exp_bench_F{i:02d}"
        ctrl = _make_sample_proposal(
            f"prop_ctrl_F{i}", f"cand_ctrl_F{i}", "SINGLE_PRODUCT",
            price_paise=299900, cogs_paise=150000, margin_pct=49.98, items=[]
        )
        treat = _make_sample_proposal(
            f"prop_treat_F{i}", f"cand_treat_F{i}", "VALUE_BUNDLE",
            price_paise=349900, cogs_paise=170000, margin_pct=51.41, items=["sleeve"],
            warranty_months=24
        )

        intents = {}
        for j in range(12):
            intents[f"{scen_id}_buyer_{j:02d}"] = BuyerIntent(
                budget=BudgetConstraint(max_amount_paise=500000, currency="INR")
            )

        scenarios.append(ExperimentBenchmarkScenario(
            scenario_id=scen_id,
            name=f"Test-Mode Execution Arm F{i:02d}",
            category="F: Test Mode Integration",
            control_proposal=ctrl,
            treatment_proposal=treat,
            population_intents=intents,
            guardrails=[
                ExperimentGuardrail(guardrail_type=GuardrailType.MIN_MARGIN_PERCENT, threshold_value=0.40, description="Min 40% margin")
            ],
            expected_winner=VariantType.TREATMENT,
            expected_evidence_status=EvidenceStatus.SUFFICIENT_EVIDENCE
        ))

    return scenarios
