"""Deterministic Policy Validator & Financial Guardrail Gatekeeper.

Performs strict, zero-float validation on every proposed candidate strategy.
The LLM can propose. It CANNOT spend or bypass constraints.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, List, Dict, Optional, Any
from domain.commerce_schemas import MerchantCommerceContext, ProductResponse
from domain.intent_schemas import BuyerIntent, BudgetType
from domain.economics import BasketItem, evaluate_basket_economics
from services.policy.schemas import (
    PolicyCandidate,
    CandidateEconomics,
    CandidateValidationStatus,
    RejectionReason,
    StrategyType
)
from services.policy.context import (
    check_product_satisfies_exclusions,
    check_product_satisfies_hard_requirements
)


class PolicyValidator:
    """Deterministic validator enforcing inviolable merchant and buyer constraints."""

    def __init__(self):
        pass

    def validate_candidate(
        self,
        candidate: PolicyCandidate,
        intent: BuyerIntent,
        context: MerchantCommerceContext
    ) -> PolicyCandidate:
        """Evaluate a single candidate strategy against all commercial guardrails."""
        rejection_reasons: List[str] = []

        # 0. Handle NO_OFFER strategy
        if candidate.strategy_type == StrategyType.NO_OFFER:
            candidate.validation_status = CandidateValidationStatus.APPROVED
            candidate.rejection_reasons = []
            candidate.deterministic_economics = None
            return candidate

        # Check for empty products on non-NO_OFFER strategies
        if not candidate.product_ids:
            candidate.validation_status = CandidateValidationStatus.REJECTED
            candidate.rejection_reasons = [RejectionReason.ZERO_ITEMS.value]
            return candidate

        prod_map: Dict[str, ProductResponse] = {p.id: p for p in context.products}
        margin_floor = Decimal(str(context.constraints.get("minimum_margin_percent", "25.00")))
        discount_ceiling = Decimal(str(context.constraints.get("maximum_discount_percent", "8.00")))

        # 1. Catalog Existence & Ownership
        candidate_products: List[ProductResponse] = []
        for pid in candidate.product_ids:
            if pid not in prod_map:
                rejection_reasons.append(RejectionReason.UNKNOWN_PRODUCT.value)
                continue
            prod = prod_map[pid]
            if prod.merchant_id != context.merchant_id:
                rejection_reasons.append(RejectionReason.CROSS_MERCHANT_PRODUCT.value)
                continue
            if not prod.is_active:
                rejection_reasons.append(RejectionReason.INACTIVE_PRODUCT.value)
            candidate_products.append(prod)

        if len(candidate_products) != len(candidate.product_ids):
            # Missing or invalid products found
            candidate.validation_status = CandidateValidationStatus.REJECTED
            candidate.rejection_reasons = rejection_reasons
            return candidate

        # 2. Inventory Availability
        req_qty = intent.quantity or 1
        for prod in candidate_products:
            if prod.available_to_sell < req_qty:
                rejection_reasons.append(RejectionReason.OUT_OF_STOCK.value)

        # 3. Buyer Exclusions (Zero Tolerance)
        if intent.exclusions:
            for prod in candidate_products:
                if not check_product_satisfies_exclusions(prod, intent.exclusions):
                    rejection_reasons.append(RejectionReason.EXCLUDED_BY_BUYER.value)

        # 4. Buyer Hard Requirements
        if intent.requirements:
            # Primary product (first in list) must satisfy core requirements
            primary_prod = candidate_products[0]
            if not check_product_satisfies_hard_requirements(primary_prod, intent.requirements):
                rejection_reasons.append(RejectionReason.REQUIREMENT_NOT_MET.value)

        # 5. Product Relationship Validity for Bundles
        if candidate.strategy_type in [StrategyType.COMPLEMENTARY_BUNDLE, StrategyType.VALUE_BUNDLE]:
            if len(candidate_products) > 1:
                primary_id = candidate_products[0].id
                bundled_ids = [p.id for p in candidate_products[1:]]

                # Check if all bundled items have valid relationship with primary item
                known_relations = {
                    (r.primary_product_id, r.related_product_id, r.relationship_type)
                    for r in context.relationships
                }
                for b_id in bundled_ids:
                    has_rel = any(
                        (primary_id == r.primary_product_id and b_id == r.related_product_id) or
                        (b_id == r.primary_product_id and primary_id == r.related_product_id)
                        for r in context.relationships
                    )
                    if not has_rel:
                        rejection_reasons.append(RejectionReason.INVALID_RELATIONSHIP.value)

        # 6. Calculate Deterministic Economics
        basket_items = [
            BasketItem(
                product_id=p.id,
                quantity=req_qty if idx == 0 else 1,  # Primary item respects requested qty
                unit_price_paise=p.price_paise,
                unit_cost_paise=p.cost_paise
            )
            for idx, p in enumerate(candidate_products)
        ]

        # Calculate proposed discount
        baseline_revenue = sum(item.unit_price_paise * item.quantity for item in basket_items)
        discount_paise = 0
        if candidate.incentive and candidate.incentive.discount_percent is not None:
            disc_pct = candidate.incentive.discount_percent
            if disc_pct > 0:
                discount_paise = int(
                    (Decimal(baseline_revenue) * (disc_pct / Decimal(100))).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )

        try:
            economics = evaluate_basket_economics(
                items=basket_items,
                promotional_discount_paise=discount_paise,
                minimum_margin_percent=margin_floor,
                maximum_discount_percent=discount_ceiling
            )

            # Check Margin Floor
            if economics.gross_margin_percent < margin_floor:
                rejection_reasons.append(RejectionReason.MARGIN_TOO_LOW.value)

            # Check Discount Ceiling
            if economics.effective_discount_percent > discount_ceiling:
                rejection_reasons.append(RejectionReason.DISCOUNT_TOO_HIGH.value)

            candidate_econ = CandidateEconomics(
                gross_revenue_paise=baseline_revenue,
                promotional_discount_paise=discount_paise,
                net_revenue_paise=economics.gross_revenue_paise,  # net payable
                total_cogs_paise=economics.total_cogs_paise,
                gross_profit_paise=economics.gross_profit_paise,
                gross_margin_percent=economics.gross_margin_percent,
                effective_discount_percent=economics.effective_discount_percent,
                is_compliant=economics.is_compliant
            )
            candidate.deterministic_economics = candidate_econ

            # 7. Buyer Budget Compliance
            if intent.budget:
                net_payable = economics.gross_revenue_paise
                if intent.budget.budget_type == BudgetType.MAX and intent.budget.max_amount_paise is not None:
                    if net_payable > intent.budget.max_amount_paise:
                        rejection_reasons.append(RejectionReason.OVER_BUDGET.value)
                elif intent.budget.budget_type == BudgetType.RANGE:
                    if intent.budget.max_amount_paise and net_payable > intent.budget.max_amount_paise:
                        rejection_reasons.append(RejectionReason.OVER_BUDGET.value)

        except ValueError as e:
            rejection_reasons.append(f"ECONOMICS_ERROR: {str(e)}")

        # Deduplicate rejection reasons
        unique_rejections = sorted(list(set(rejection_reasons)))
        candidate.rejection_reasons = unique_rejections

        if len(unique_rejections) == 0:
            candidate.validation_status = CandidateValidationStatus.APPROVED
        else:
            candidate.validation_status = CandidateValidationStatus.REJECTED

        return candidate
