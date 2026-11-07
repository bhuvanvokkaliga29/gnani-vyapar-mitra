"""Execution-Time Deterministic Validator for Phase 5 Execution Gate.

Independently inspects fresh merchant state, recalculates unit economics in integer paise,
and enforces commercial guardrails before any financial authorization.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Optional, Set
import structlog

from domain.commerce_schemas import MerchantCommerceContext, ProductResponse
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import (
    PolicyProposal,
    PolicyCandidate,
    CandidateEconomics,
    StrategyType,
    CandidateValidationStatus
)
from services.policy.context import (
    check_product_satisfies_exclusions,
    check_product_satisfies_hard_requirements
)
from services.execution.schemas import ExecutionRejectionReason

logger = structlog.get_logger()


class ExecutionValidator:
    """Authoritative execution-time gatekeeper validating against fresh database state."""

    VALIDATION_VERSION = "execution-gate/v1"

    def revalidate_candidate(
        self,
        candidate: PolicyCandidate,
        proposal: PolicyProposal,
        fresh_context: MerchantCommerceContext,
        intent: Optional[BuyerIntent] = None
    ) -> Tuple[bool, List[ExecutionRejectionReason], Optional[CandidateEconomics], int]:
        """Revalidate a proposed candidate against fresh merchant state.

        Returns:
            (is_authorized, rejection_reasons, recalculated_economics, authorized_amount_paise)
        """
        rejection_reasons: List[ExecutionRejectionReason] = []

        # 1. Proposal Integrity & Non-Executable Offer Checks
        if proposal.merchant_id != fresh_context.merchant_id:
            rejection_reasons.append(ExecutionRejectionReason.MERCHANT_MISMATCH)

        if candidate.strategy_type == StrategyType.NO_OFFER:
            rejection_reasons.append(ExecutionRejectionReason.NO_EXECUTABLE_OFFER)

        if candidate.validation_status != CandidateValidationStatus.APPROVED:
            rejection_reasons.append(ExecutionRejectionReason.INVALID_PROPOSAL_STATUS)

        if candidate.candidate_id not in [c.candidate_id for c in proposal.candidates]:
            rejection_reasons.append(ExecutionRejectionReason.INVALID_PROPOSAL_STATUS)

        if not candidate.product_ids and candidate.strategy_type != StrategyType.NO_OFFER:
            rejection_reasons.append(ExecutionRejectionReason.PRODUCT_UNAVAILABLE)

        # Build fresh product lookup
        fresh_products: dict[str, ProductResponse] = {p.id: p for p in fresh_context.products}

        # Determine component quantities
        quantities: dict[str, int] = {}
        if candidate.bundle_components:
            for comp in candidate.bundle_components:
                pid = comp.get("product_id")
                qty = comp.get("quantity", 1)
                if pid:
                    quantities[pid] = quantities.get(pid, 0) + qty
        else:
            for pid in candidate.product_ids:
                quantities[pid] = 1

        # 2. Product Validity & Stock Checks against Fresh State
        for pid, qty in quantities.items():
            if pid not in fresh_products:
                rejection_reasons.append(ExecutionRejectionReason.PRODUCT_UNAVAILABLE)
                continue

            fresh_p = fresh_products[pid]

            if fresh_p.merchant_id != fresh_context.merchant_id:
                rejection_reasons.append(ExecutionRejectionReason.MERCHANT_MISMATCH)

            if not fresh_p.is_active:
                rejection_reasons.append(ExecutionRejectionReason.PRODUCT_UNAVAILABLE)

            if fresh_p.currency != fresh_context.currency:
                rejection_reasons.append(ExecutionRejectionReason.CURRENCY_MISMATCH)

            # Available-to-sell inventory check against fresh state
            if fresh_p.available_to_sell < qty:
                rejection_reasons.append(ExecutionRejectionReason.OUT_OF_STOCK)

            # Buyer constraints checks if intent supplied
            if intent:
                if intent.exclusions and not check_product_satisfies_exclusions(fresh_p, intent.exclusions):
                    rejection_reasons.append(ExecutionRejectionReason.BUYER_EXCLUSION_VIOLATED)

                if intent.requirements and not check_product_satisfies_hard_requirements(fresh_p, intent.requirements):
                    rejection_reasons.append(ExecutionRejectionReason.BUYER_REQUIREMENT_CHANGED)

        # 3. Product Relationship Integrity for Bundles
        if candidate.strategy_type in [StrategyType.COMPLEMENTARY_BUNDLE, StrategyType.VALUE_BUNDLE]:
            if len(candidate.product_ids) >= 2:
                primary_id = candidate.product_ids[0]
                related_ids = set(candidate.product_ids[1:])
                valid_related = {
                    r.related_product_id
                    for r in fresh_context.relationships
                    if r.primary_product_id == primary_id and r.relationship_type in ["COMPLEMENTARY", "BUNDLE_COMPONENT"]
                }
                if not related_ids.issubset(valid_related):
                    rejection_reasons.append(ExecutionRejectionReason.RELATIONSHIP_INVALID)

        # 4. Deterministic Economics Recalculation against Fresh State
        gross_revenue_paise = 0
        total_cogs_paise = 0

        for pid, qty in quantities.items():
            if pid in fresh_products:
                fresh_p = fresh_products[pid]
                gross_revenue_paise += fresh_p.price_paise * qty
                total_cogs_paise += fresh_p.cost_paise * qty

        # Discount handling
        discount_percent = Decimal("0.00")
        promotional_discount_paise = 0

        if candidate.incentive and candidate.incentive.incentive_type == "discount":
            if candidate.incentive.discount_percent:
                discount_percent = Decimal(str(candidate.incentive.discount_percent))

        max_allowed_discount = Decimal(str(fresh_context.constraints.get("maximum_discount_percent", 8.00)))
        if discount_percent > max_allowed_discount:
            rejection_reasons.append(ExecutionRejectionReason.DISCOUNT_TOO_HIGH)

        if gross_revenue_paise > 0 and discount_percent > Decimal("0.00"):
            disc_raw = (Decimal(gross_revenue_paise) * discount_percent / Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            promotional_discount_paise = int(disc_raw)

        net_revenue_paise = max(0, gross_revenue_paise - promotional_discount_paise)
        gross_profit_paise = net_revenue_paise - total_cogs_paise

        if net_revenue_paise > 0:
            margin_decimal = (Decimal(gross_profit_paise) / Decimal(net_revenue_paise)) * Decimal("100")
            gross_margin_percent = margin_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            gross_margin_percent = Decimal("0.00")

        min_margin = Decimal(str(fresh_context.constraints.get("minimum_margin_percent", 25.00)))
        if gross_margin_percent < min_margin:
            rejection_reasons.append(ExecutionRejectionReason.MARGIN_TOO_LOW)

        # Buyer budget constraint verification
        if intent and intent.budget and intent.budget.max_amount_paise:
            if net_revenue_paise > intent.budget.max_amount_paise:
                rejection_reasons.append(ExecutionRejectionReason.OVER_BUDGET)

        is_compliant = (len(rejection_reasons) == 0)

        effective_disc_pct = Decimal("0.00")
        if gross_revenue_paise > 0 and promotional_discount_paise > 0:
            effective_disc_pct = (
                (Decimal(promotional_discount_paise) / Decimal(gross_revenue_paise)) * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        recalculated_economics = CandidateEconomics(
            gross_revenue_paise=gross_revenue_paise,
            promotional_discount_paise=promotional_discount_paise,
            net_revenue_paise=net_revenue_paise,
            total_cogs_paise=total_cogs_paise,
            gross_profit_paise=gross_profit_paise,
            gross_margin_percent=gross_margin_percent,
            effective_discount_percent=effective_disc_pct,
            is_compliant=is_compliant
        )

        authorized_amount_paise = net_revenue_paise if is_compliant else 0

        # Remove duplicate rejection reasons while preserving order
        seen = set()
        deduped_reasons = []
        for r in rejection_reasons:
            if r not in seen:
                seen.add(r)
                deduped_reasons.append(r)

        return (is_compliant, deduped_reasons, recalculated_economics, authorized_amount_paise)
