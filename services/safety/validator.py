"""Deterministic Policy Safety & Admissibility Validator.

Contract Version: policy-safety/v1
Enforces inviolable commercial safety checks against authoritative fresh database state.

CRITICAL INVARIANTS:
- LEARNING SCORE CANNOT OVERRIDE HARD SAFETY.
- Candidate is evaluated strictly against fresh MerchantCommerceContext.
- NO_OFFER is admissible without requiring inventory.
- Zero execution authority (does not create orders or reserve stock).
- Deterministic failure sorting based on canonical domain priority.
"""

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Optional, Set, Dict
import structlog

from domain.commerce_schemas import MerchantCommerceContext, ProductResponse
from domain.intent_schemas import BuyerIntent
from services.policy.schemas import (
    PolicyCandidate,
    CandidateEconomics,
    StrategyType,
    CandidateValidationStatus
)
from services.policy.context import (
    check_product_satisfies_exclusions,
    check_product_satisfies_hard_requirements
)
from services.safety.schemas import (
    PolicySafetyStatus,
    PolicySafetyFailureCode,
    FAILURE_CODE_PRIORITY
)

logger = structlog.get_logger()


class PolicySafetyValidator:
    """Authoritative deterministic gatekeeper evaluating candidate policy admissibility."""

    VALIDATION_VERSION = "policy-safety/v1"

    @classmethod
    def compute_state_fingerprint(
        cls,
        candidate: PolicyCandidate,
        fresh_context: MerchantCommerceContext,
        proposed_policy_version: str = "merchant-policy/v1"
    ) -> str:
        """Compute a deterministic fingerprint of authoritative state relevant to this candidate.
        
        Captures:
        - merchant_id
        - proposed_policy_version
        - merchant constraints (minimum_margin_percent, maximum_discount_percent)
        - relevant catalog products (price, cost, available_to_sell, is_active, currency)
        - relevant bundle relationships
        """
        prod_map = {p.id: p for p in fresh_context.products}
        relevant_prods = []
        for pid in sorted(candidate.product_ids):
            if pid in prod_map:
                p = prod_map[pid]
                relevant_prods.append({
                    "id": p.id,
                    "price_paise": p.price_paise,
                    "cost_paise": p.cost_paise,
                    "available_to_sell": p.available_to_sell,
                    "is_active": p.is_active,
                    "currency": p.currency
                })
            else:
                relevant_prods.append({"id": pid, "missing": True})

        relevant_rels = []
        if candidate.strategy_type in [StrategyType.COMPLEMENTARY_BUNDLE, StrategyType.VALUE_BUNDLE]:
            for r in sorted(fresh_context.relationships, key=lambda x: (x.primary_product_id, x.related_product_id)):
                if r.primary_product_id in candidate.product_ids or r.related_product_id in candidate.product_ids:
                    relevant_rels.append({
                        "primary": r.primary_product_id,
                        "related": r.related_product_id,
                        "type": r.relationship_type
                    })

        state_dict = {
            "merchant_id": fresh_context.merchant_id,
            "policy_version": proposed_policy_version,
            "constraints": {
                "min_margin": str(fresh_context.constraints.get("minimum_margin_percent", 25.0)),
                "max_discount": str(fresh_context.constraints.get("maximum_discount_percent", 8.0))
            },
            "products": relevant_prods,
            "relationships": relevant_rels
        }
        serialized = json.dumps(state_dict, sort_keys=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"ctx_{digest}"

    @classmethod
    def validate_admissibility(
        cls,
        candidate: PolicyCandidate,
        fresh_context: MerchantCommerceContext,
        merchant_id: str,
        proposed_policy_version: str = "merchant-policy/v1",
        intent: Optional[BuyerIntent] = None
    ) -> Tuple[PolicySafetyStatus, List[PolicySafetyFailureCode], Optional[CandidateEconomics], str]:
        """Deterministically evaluate if candidate policy is safe and admissible.
        
        Returns:
            (status, sorted_failure_codes, recalculated_economics, validation_reason)
        """
        encountered_failures: Set[PolicySafetyFailureCode] = set()

        # 1. Merchant Scope Check
        if merchant_id != fresh_context.merchant_id:
            encountered_failures.add(PolicySafetyFailureCode.MERCHANT_SCOPE_MISMATCH)

        # 2. Policy Identity & Structural Validity
        if not candidate.candidate_id or not candidate.candidate_id.strip():
            encountered_failures.add(PolicySafetyFailureCode.POLICY_NOT_FOUND)

        if candidate.validation_status == CandidateValidationStatus.REJECTED:
            encountered_failures.add(PolicySafetyFailureCode.INVALID_POLICY)

        if proposed_policy_version != "merchant-policy/v1":
            encountered_failures.add(PolicySafetyFailureCode.POLICY_VERSION_INVALID)

        # 3. Special Handling for NO_OFFER
        # NO_OFFER does not require inventory or product catalog presence.
        if candidate.strategy_type == StrategyType.NO_OFFER:
            # If structural or merchant scope errors occurred, fail closed
            if encountered_failures:
                sorted_failures = sorted(encountered_failures, key=lambda f: FAILURE_CODE_PRIORITY.get(f, 999))
                return (PolicySafetyStatus.REJECTED, sorted_failures, None, sorted_failures[0].value)

            no_offer_econ = CandidateEconomics(
                gross_revenue_paise=0,
                promotional_discount_paise=0,
                net_revenue_paise=0,
                total_cogs_paise=0,
                gross_profit_paise=0,
                gross_margin_percent=Decimal("0.00"),
                effective_discount_percent=Decimal("0.00"),
                is_compliant=True
            )
            return (
                PolicySafetyStatus.ADMISSIBLE,
                [],
                no_offer_econ,
                "ADMISSIBLE_ALL_CONSTRAINTS_SATISFIED"
            )

        # 4. Catalog Products & Quantities
        if not candidate.product_ids:
            encountered_failures.add(PolicySafetyFailureCode.PRODUCT_NOT_FOUND)

        fresh_products: Dict[str, ProductResponse] = {p.id: p for p in fresh_context.products}

        quantities: Dict[str, int] = {}
        if candidate.bundle_components:
            for comp in candidate.bundle_components:
                pid = comp.get("product_id")
                qty = comp.get("quantity", 1)
                if pid:
                    quantities[pid] = quantities.get(pid, 0) + qty
        else:
            for pid in candidate.product_ids:
                quantities[pid] = quantities.get(pid, 0) + 1

        # 5. Product Integrity & Inventory Check against Fresh State
        for pid, qty in quantities.items():
            if pid not in fresh_products:
                encountered_failures.add(PolicySafetyFailureCode.PRODUCT_NOT_FOUND)
                continue

            p = fresh_products[pid]

            if p.merchant_id != fresh_context.merchant_id:
                encountered_failures.add(PolicySafetyFailureCode.MERCHANT_SCOPE_MISMATCH)

            if not p.is_active or p.currency != fresh_context.currency:
                encountered_failures.add(PolicySafetyFailureCode.PRODUCT_INELIGIBLE)

            # Check fresh inventory availability
            if p.available_to_sell < qty:
                encountered_failures.add(PolicySafetyFailureCode.INVENTORY_INSUFFICIENT)

            # Buyer exclusions / hard requirements if intent supplied
            if intent:
                if intent.exclusions and not check_product_satisfies_exclusions(p, intent.exclusions):
                    encountered_failures.add(PolicySafetyFailureCode.PRODUCT_INELIGIBLE)
                if intent.requirements and not check_product_satisfies_hard_requirements(p, intent.requirements):
                    encountered_failures.add(PolicySafetyFailureCode.PRODUCT_INELIGIBLE)

        # 6. Bundle Relationship Integrity
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
                    encountered_failures.add(PolicySafetyFailureCode.RELATIONSHIP_INVALID)

        # 7. Deterministic Economics Recalculation against Fresh DB State
        gross_revenue_paise = 0
        total_cogs_paise = 0

        try:
            for pid, qty in quantities.items():
                if pid in fresh_products:
                    p = fresh_products[pid]
                    gross_revenue_paise += p.price_paise * qty
                    total_cogs_paise += p.cost_paise * qty

            discount_percent = Decimal("0.00")
            promotional_discount_paise = 0

            if candidate.incentive and candidate.incentive.incentive_type == "discount":
                if candidate.incentive.discount_percent:
                    discount_percent = Decimal(str(candidate.incentive.discount_percent))

            # Discount Ceiling Check
            max_allowed_discount = Decimal(str(fresh_context.constraints.get("maximum_discount_percent", 8.00)))
            if discount_percent > max_allowed_discount:
                encountered_failures.add(PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED)

            if gross_revenue_paise > 0 and discount_percent > Decimal("0.00"):
                disc_raw = (Decimal(gross_revenue_paise) * discount_percent / Decimal("100")).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                promotional_discount_paise = int(disc_raw)

            net_revenue_paise = max(0, gross_revenue_paise - promotional_discount_paise)
            gross_profit_paise = net_revenue_paise - total_cogs_paise

            if net_revenue_paise > 0:
                margin_dec = (Decimal(gross_profit_paise) / Decimal(net_revenue_paise)) * Decimal("100")
                gross_margin_percent = margin_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                gross_margin_percent = Decimal("0.00")

            # Margin / Contribution Floor Check
            min_margin = Decimal(str(fresh_context.constraints.get("minimum_margin_percent", 25.00)))
            if gross_margin_percent < min_margin:
                encountered_failures.add(PolicySafetyFailureCode.CONTRIBUTION_FLOOR_VIOLATED)

            # Buyer Budget Ceiling Check
            if intent and intent.budget and intent.budget.max_amount_paise:
                if net_revenue_paise > intent.budget.max_amount_paise:
                    encountered_failures.add(PolicySafetyFailureCode.BUDGET_LIMIT_EXCEEDED)

            effective_disc_pct = Decimal("0.00")
            if gross_revenue_paise > 0 and promotional_discount_paise > 0:
                effective_disc_pct = (
                    (Decimal(promotional_discount_paise) / Decimal(gross_revenue_paise)) * Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            is_compliant = (len(encountered_failures) == 0)

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
        except Exception as e:
            logger.error("safety_economics_recalculation_failed", error=str(e))
            encountered_failures.add(PolicySafetyFailureCode.ECONOMICS_RECALCULATION_FAILED)
            recalculated_economics = None

        # 8. Sort Failures by Deterministic Canonical Priority
        sorted_failures = sorted(encountered_failures, key=lambda f: FAILURE_CODE_PRIORITY.get(f, 999))

        if not sorted_failures:
            return (
                PolicySafetyStatus.ADMISSIBLE,
                [],
                recalculated_economics,
                "ADMISSIBLE_ALL_CONSTRAINTS_SATISFIED"
            )

        return (
            PolicySafetyStatus.REJECTED,
            sorted_failures,
            recalculated_economics,
            sorted_failures[0].value
        )
