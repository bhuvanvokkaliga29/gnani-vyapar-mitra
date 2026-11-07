"""Context & Product Eligibility Helpers for Policy Agent Reasoning.

Deterministically pre-filters catalog products and extracts relevant
relationships before LLM strategy generation to prevent token waste and hallucinations.
"""

from typing import List, Dict, Any, Optional, Set
from domain.commerce_schemas import MerchantCommerceContext, ProductResponse, RelationshipResponse
from domain.intent_schemas import BuyerIntent, AttributeRequirement, ExclusionConstraint, OperatorType


def check_product_satisfies_exclusions(product: ProductResponse, exclusions: List[ExclusionConstraint]) -> bool:
    """Return False if product contains any attribute value explicitly forbidden by the buyer."""
    attrs = product.attributes or {}
    for excl in exclusions:
        attr_val = attrs.get(excl.attribute)
        if attr_val is not None and str(attr_val).lower() == excl.excluded_value.lower():
            return False
        # Also check name and category as safeguards
        if excl.excluded_value.lower() in product.name.lower():
            return False
        if excl.excluded_value.lower() in product.category.lower():
            return False
    return True


def check_product_satisfies_hard_requirements(product: ProductResponse, requirements: List[AttributeRequirement]) -> bool:
    """Check if a product satisfies all explicit buyer HARD requirements."""
    attrs = product.attributes or {}

    for req in requirements:
        attr_val = attrs.get(req.attribute)

        # 1. Laptop size requirement
        if req.attribute == "laptop_size":
            if attr_val is None:
                # If product doesn't state laptop compatibility, check description or name
                # If it's a general backpack with no size specified, don't reject outright unless category is sleeve
                continue
            try:
                prod_size = float(attr_val)
                req_size = float(req.value)
                if req.operator == OperatorType.GTE and prod_size < req_size:
                    return False
                elif req.operator == OperatorType.EQ and prod_size != req_size:
                    return False
            except (ValueError, TypeError):
                return False

        # 2. Water resistance requirement
        elif req.attribute in ["water_resistant", "water_resistance"]:
            if attr_val is None:
                # If not specified in attributes, check description
                is_wr = "waterproof" in product.name.lower() or (product.description and "waterproof" in product.description.lower())
                if req.value is True and not is_wr:
                    return False
            elif bool(attr_val) != bool(req.value):
                return False

        # 3. Generic equality match
        elif req.operator == OperatorType.EQ:
            if attr_val is not None:
                if str(attr_val).lower() != str(req.value).lower():
                    return False
            else:
                # Check description/name for mention of the required feature
                target_str = str(req.value).lower()
                desc_text = (product.description or "").lower() + " " + product.name.lower()
                if target_str not in desc_text:
                    return False

    return True


def filter_eligible_products(
    context: MerchantCommerceContext,
    intent: Optional[BuyerIntent] = None
) -> List[ProductResponse]:
    """Deterministically pre-filter catalog to products eligible for the buyer.

    Filters by:
    1. Active status (is_active == True)
    2. In-stock (available_to_sell > 0)
    3. Merchant ownership
    4. Currency match
    5. Buyer exclusions (zero tolerance for excluded materials/colors)
    6. Buyer hard requirements
    7. Buyer category match (if category specified; only complementary items to matching products are included)
    """
    candidates_base: List[ProductResponse] = []

    for p in context.products:
        if not p.is_active:
            continue
        if p.available_to_sell <= 0:
            continue
        if p.merchant_id != context.merchant_id:
            continue
        if p.currency != context.currency:
            continue

        if intent:
            if intent.exclusions and not check_product_satisfies_exclusions(p, intent.exclusions):
                continue
            if intent.requirements and not check_product_satisfies_hard_requirements(p, intent.requirements):
                continue

        candidates_base.append(p)

    if not intent or not intent.category:
        return candidates_base

    # Find products matching the requested category
    req_cat = intent.category.lower()
    cat_matches = [
        p for p in candidates_base
        if (p.category.lower() == req_cat or
            req_cat in p.category.lower() or
            p.category.lower() in req_cat)
    ]

    # If NO product matches the requested category, return empty (triggers NO_OFFER)
    if not cat_matches:
        return []

    # Include matching primary items plus accessories complementary to matching primary items
    cat_match_ids = {p.id for p in cat_matches}
    complementary_ids = {
        r.related_product_id
        for r in context.relationships
        if r.primary_product_id in cat_match_ids and r.relationship_type in ["COMPLEMENTARY", "BUNDLE_COMPONENT"]
    }

    # Order primary category items first, then complements
    eligible = [p for p in candidates_base if p.id in cat_match_ids]
    for p in candidates_base:
        if p.id in complementary_ids and p.id not in cat_match_ids:
            eligible.append(p)

    return eligible


def get_complementary_products(
    primary_product_id: str,
    context: MerchantCommerceContext
) -> List[ProductResponse]:
    """Find all in-stock products marked COMPLEMENTARY to the primary product."""
    rel_ids: Set[str] = {
        r.related_product_id
        for r in context.relationships
        if r.primary_product_id == primary_product_id and r.relationship_type == "COMPLEMENTARY"
    }

    prod_map = {p.id: p for p in context.products}
    complementary = [
        prod_map[pid]
        for pid in rel_ids
        if pid in prod_map and prod_map[pid].is_active and prod_map[pid].available_to_sell > 0
    ]
    return complementary


def get_substitute_products(
    primary_product_id: str,
    context: MerchantCommerceContext
) -> List[ProductResponse]:
    """Find all in-stock products marked SUBSTITUTE to the primary product."""
    rel_ids: Set[str] = {
        r.related_product_id
        for r in context.relationships
        if r.primary_product_id == primary_product_id and r.relationship_type == "SUBSTITUTE"
    }

    prod_map = {p.id: p for p in context.products}
    return [
        prod_map[pid]
        for pid in rel_ids
        if pid in prod_map and prod_map[pid].is_active and prod_map[pid].available_to_sell > 0
    ]
