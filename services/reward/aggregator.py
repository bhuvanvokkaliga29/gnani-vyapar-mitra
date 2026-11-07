"""Objective Aggregator: Computes the Primary Learning Objective across eligible opportunities.

Formula:
Observed Contribution per AI Shopper = Sum(Observed Contribution) / Eligible AI Shoppers
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict
from services.reward.schemas import (
    PolicyOpportunityReward,
    AggregatedRewardObjective,
    RewardState,
    ObjectiveMetricType
)
from services.reward.errors import (
    ZeroDenominatorError,
    RewardAttributionError,
    IneligibleRewardError
)


class ObjectiveAggregator:
    """Computes deterministic learning objectives over populations of opportunity rewards."""

    @classmethod
    def aggregate_objective(
        cls,
        rewards: List[PolicyOpportunityReward],
        metric_type: ObjectiveMetricType = ObjectiveMetricType.OBSERVED_CONTRIBUTION_PER_SHOPPER
    ) -> AggregatedRewardObjective:
        """Aggregate opportunity rewards into the primary learning objective."""
        if not rewards:
            raise ZeroDenominatorError("Cannot aggregate objective over an empty rewards list.")

        # 1. Tenant & Policy Attribution Isolation
        merchant_id = rewards[0].merchant_id
        policy_id = rewards[0].policy_id
        policy_version = rewards[0].policy_version
        experiment_id = rewards[0].experiment_id
        variant = rewards[0].variant
        buyer_context_key = rewards[0].buyer_context_key

        for r in rewards:
            if r.merchant_id != merchant_id:
                raise RewardAttributionError(
                    f"Cross-tenant reward aggregation forbidden: '{r.merchant_id}' != '{merchant_id}'."
                )
            if r.policy_id != policy_id:
                raise RewardAttributionError(
                    f"Cross-policy reward aggregation forbidden: '{r.policy_id}' != '{policy_id}'."
                )

        # 2. Partition Admissible vs. Inadmissible
        total_eval = len(rewards)
        admissible_rewards = [r for r in rewards if r.is_admissible]
        ineligible_count = total_eval - len(admissible_rewards)

        # 3. DENOMINATOR ENFORCEMENT
        eligible_opportunity_count = len(admissible_rewards)
        if eligible_opportunity_count == 0:
            raise ZeroDenominatorError(
                f"Eligible opportunity count is 0 (all {total_eval} opportunities were ineligible/corrupted). "
                "The objective is undefined."
            )

        # 4. NUMERATOR ENFORCEMENT
        # Sum of contribution across ALL eligible opportunities (including 0s for non-purchases)
        total_contrib_paise = sum(r.reward_contribution_paise for r in admissible_rewards)
        total_rev_paise = sum(r.realized_revenue_paise for r in admissible_rewards)
        total_cogs_paise = sum(r.realized_cogs_paise for r in admissible_rewards)
        total_disc_paise = sum(r.realized_discount_paise for r in admissible_rewards)

        # 5. Primary Learning Objective Calculation
        # Exact Decimal division
        contrib_dec = Decimal(total_contrib_paise)
        opps_dec = Decimal(eligible_opportunity_count)
        contrib_per_shopper_dec = float((contrib_dec / opps_dec).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
        contrib_per_shopper_int = int((contrib_dec / opps_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # 6. Secondary Funnel & Margin Metrics
        successful_payment_count = sum(
            1 for r in admissible_rewards if r.reward_state == RewardState.REWARD_ELIGIBLE and r.reward_contribution_paise > 0
        )
        successful_payment_rate = round(successful_payment_count / eligible_opportunity_count, 4)

        # 7. Safety Invariant & Policy Admissibility
        # Guardrail-violating opportunities remain in the denominator (diluting average contribution)
        # and explicitly flag the policy as inadmissible for promotion.
        guardrail_violation_count = sum(
            1 for r in admissible_rewards
            if r.reward_state == RewardState.REWARD_GUARDRAIL_VIOLATION or r.is_safety_violation
        )
        is_policy_admissible = (guardrail_violation_count == 0)

        if total_rev_paise > 0:
            rev_d = Decimal(total_rev_paise)
            cogs_d = Decimal(total_cogs_paise)
            avg_margin_pct = float((((rev_d - cogs_d) / rev_d) * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            avg_margin_pct = 0.0

        all_bcks = {r.buyer_context_key for r in rewards if r.buyer_context_key}
        scoped_bck = list(all_bcks)[0] if len(all_bcks) == 1 else "ALL_CONTEXTS"
        aggregation_key = f"{merchant_id}:{scoped_bck}:{policy_id}:{policy_version}"

        return AggregatedRewardObjective(
            objective_id=f"obj_{uuid.uuid4().hex[:12]}",
            objective_version="merchant-reward/v1",
            formula_version="contribution-formula/v1",
            merchant_id=merchant_id,
            policy_id=policy_id,
            policy_version=policy_version,
            buyer_context_key=scoped_bck,
            experiment_id=experiment_id,
            variant=variant,
            metric_type=metric_type,
            total_opportunities_evaluated=total_eval,
            eligible_opportunity_count=eligible_opportunity_count,
            ineligible_opportunity_count=ineligible_count,
            order_created_count=sum(1 for r in admissible_rewards if r.realized_revenue_paise > 0),
            successful_payment_count=successful_payment_count,
            successful_payment_rate=successful_payment_rate,
            guardrail_violation_count=guardrail_violation_count,
            is_policy_admissible=is_policy_admissible,
            total_realized_revenue_paise=total_rev_paise,
            total_realized_cogs_paise=total_cogs_paise,
            total_realized_discount_paise=total_disc_paise,
            total_contribution_paise=total_contrib_paise,
            contribution_per_shopper_paise=contrib_per_shopper_int,
            contribution_per_shopper_decimal=contrib_per_shopper_dec,
            average_margin_percent=avg_margin_pct,
            aggregation_key=aggregation_key
        )
