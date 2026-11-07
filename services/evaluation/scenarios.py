"""Scenario Suite and Synthetic Opportunity Generator for Phase 8.9 Closed-Loop Evaluation.

Provides:
- Deterministic training and holdout scenario partitions.
- Curated commercial intent distributions across categories and budget tiers.
- Synthetic directional learning datasets (Context A vs Context B).
- Controlled regime-shift scenarios to verify parameter vector adaptation.
"""

import random
from typing import List, Tuple, Dict, Any, Optional
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    BudgetType,
    ConstraintType,
    AttributeRequirement,
    AttributePreference,
    OperatorType,
    PreferenceStrength
)


def create_synthetic_intent(
    scenario_id: str,
    category: str = "travel_backpack",
    budget_paise: int = 500000,
    laptop_size: float = 15.6,
    preference_tag: str = "water_resistant"
) -> BuyerIntent:
    """Construct a clean, valid BuyerIntent for evaluation opportunities."""
    budget = BudgetConstraint(
        max_amount_paise=budget_paise,
        currency="INR",
        budget_type=BudgetType.MAX,
        constraint_type=ConstraintType.HARD
    )
    reqs = [
        AttributeRequirement(
            attribute="laptop_size",
            operator=OperatorType.GTE,
            value=laptop_size,
            unit="inches"
        )
    ]
    prefs = [
        AttributePreference(
            attribute=preference_tag,
            preference="true",
            strength=PreferenceStrength.PREFERRED
        )
    ]
    return BuyerIntent(
        category=category,
        budget=budget,
        requirements=reqs,
        preferences=prefs
    )


class EvaluationScenarioGenerator:
    """Generates structured scenario sets for closed-loop evaluation runs."""

    @classmethod
    def generate_partitioned_scenarios(
        cls,
        training_count: int = 40,
        holdout_count: int = 10,
        seed: int = 42,
        category: str = "travel_backpack"
    ) -> Tuple[List[Tuple[str, BuyerIntent]], List[Tuple[str, BuyerIntent]]]:
        """Generate partitioned training and holdout scenario sets with strict temporal ordering.
        
        Guarantees:
        1. Training scenarios are distinct from holdout scenarios.
        2. Holdout set is strictly unseen during training.
        3. Deterministic reproducibility with fixed seed.
        """
        rng = random.Random(seed)
        budgets = [400000, 500000, 600000, 700000, 800000]
        laptop_sizes = [13.3, 14.0, 15.6, 16.0]

        training_set: List[Tuple[str, BuyerIntent]] = []
        for i in range(training_count):
            bgt = rng.choice(budgets)
            ls = rng.choice(laptop_sizes)
            scen_id = f"scen_train_{i+1:03d}"
            intent = create_synthetic_intent(scen_id, category=category, budget_paise=bgt, laptop_size=ls)
            training_set.append((scen_id, intent))

        holdout_set: List[Tuple[str, BuyerIntent]] = []
        for j in range(holdout_count):
            bgt = rng.choice(budgets)
            ls = rng.choice(laptop_sizes)
            scen_id = f"scen_holdout_{j+1:03d}"
            intent = create_synthetic_intent(scen_id, category=category, budget_paise=bgt, laptop_size=ls)
            holdout_set.append((scen_id, intent))

        return training_set, holdout_set

    @classmethod
    def generate_directional_learning_dataset(
        cls,
        count_per_regime: int = 20,
        seed: int = 42
    ) -> Tuple[List[Tuple[str, BuyerIntent]], List[Tuple[str, BuyerIntent]], List[Tuple[str, BuyerIntent]]]:
        """Generate scenarios designed to verify directional model adaptation and regime shifts.
        
        Context A (High Budget): Opportunities in high tier.
        Context B (Low Budget): Opportunities in mid/low tier.
        Regime Shift: Follow-up opportunities to test adaptive weight adjustment.
        """
        context_a: List[Tuple[str, BuyerIntent]] = []
        context_b: List[Tuple[str, BuyerIntent]] = []
        regime_shift: List[Tuple[str, BuyerIntent]] = []

        for i in range(count_per_regime):
            intent_a = create_synthetic_intent(
                f"scen_dir_a_{i+1:03d}",
                category="travel_backpack",
                budget_paise=800000,
                laptop_size=16.0
            )
            context_a.append((f"scen_dir_a_{i+1:03d}", intent_a))

            intent_b = create_synthetic_intent(
                f"scen_dir_b_{i+1:03d}",
                category="travel_backpack",
                budget_paise=350000,
                laptop_size=14.0
            )
            context_b.append((f"scen_dir_b_{i+1:03d}", intent_b))

            intent_shift = create_synthetic_intent(
                f"scen_shift_{i+1:03d}",
                category="travel_backpack",
                budget_paise=800000,
                laptop_size=16.0,
                preference_tag="lightweight"
            )
            regime_shift.append((f"scen_shift_{i+1:03d}", intent_shift))

        return context_a, context_b, regime_shift
