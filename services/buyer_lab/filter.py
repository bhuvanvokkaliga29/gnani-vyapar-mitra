"""Deterministic Eligibility Filter for AI Buyer Lab.

Enforces hard constraints, explicit exclusions, currency matching, and budget ceilings.
Core Invariant: An offer that violates ANY hard requirement or exclusion CAN NEVER WIN,
regardless of how cheap, heavily discounted, or bundled it is.
"""

from typing import List, Tuple, Dict, Any, Optional
import structlog

from domain.intent_schemas import BuyerIntent, OperatorType, ConstraintType
from services.buyer_lab.schemas import (
    BuyerOffer,
    RejectedOfferTrace,
    DecisionStepTrace,
    OfferRejectionCode
)

logger = structlog.get_logger()


class EligibilityFilter:
    """Deterministic filter evaluating candidate offers against BuyerIntent hard constraints."""

    def filter_offers(
        self,
        intent: BuyerIntent,
        offers: List[BuyerOffer]
    ) -> Tuple[List[BuyerOffer], List[RejectedOfferTrace], List[DecisionStepTrace], List[str]]:
        """Filter offers into eligible and rejected subsets with complete audit traces."""
        eligible_offers: List[BuyerOffer] = list(offers)
        rejected_traces: List[RejectedOfferTrace] = []
        step_traces: List[DecisionStepTrace] = []
        hard_constraints_checked: List[str] = []

        # -------------------------------------------------------------
        # STEP 1: Availability Filter
        # -------------------------------------------------------------
        hard_constraints_checked.append("AVAILABILITY")
        before_count = len(eligible_offers)
        surviving_step1: List[BuyerOffer] = []
        step1_rejections: List[str] = []

        for offer in eligible_offers:
            if not offer.availability:
                reason = OfferRejectionCode.UNAVAILABLE
                detail = f"Offer '{offer.offer_id}' is marked unavailable or out of stock."
                rejected_traces.append(RejectedOfferTrace(
                    offer_id=offer.offer_id,
                    merchant_id=offer.merchant_id,
                    rejection_reason=reason,
                    detail=detail
                ))
                step1_rejections.append(offer.offer_id)
            else:
                surviving_step1.append(offer)

        eligible_offers = surviving_step1
        step_traces.append(DecisionStepTrace(
            step="AVAILABILITY_FILTER",
            description="Filtered out unavailable and out-of-stock items",
            eligible_count_before=before_count,
            eligible_count_after=len(eligible_offers),
            rejections_in_step=step1_rejections
        ))

        # -------------------------------------------------------------
        # STEP 2: Currency & Budget Ceiling Filter
        # -------------------------------------------------------------
        if intent.budget:
            hard_constraints_checked.append(f"BUDGET_CEILING_{intent.budget.currency}")
            before_count = len(eligible_offers)
            surviving_step2: List[BuyerOffer] = []
            step2_rejections: List[str] = []

            for offer in eligible_offers:
                # Currency check
                if intent.budget.currency and offer.currency.upper() != intent.budget.currency.upper():
                    rejected_traces.append(RejectedOfferTrace(
                        offer_id=offer.offer_id,
                        merchant_id=offer.merchant_id,
                        rejection_reason=OfferRejectionCode.CURRENCY_MISMATCH,
                        detail=f"Offer currency '{offer.currency}' does not match requested currency '{intent.budget.currency}'."
                    ))
                    step2_rejections.append(offer.offer_id)
                    continue

                # Hard budget ceiling check
                max_budget = intent.budget.max_amount_paise or intent.budget.amount_paise
                if max_budget is not None and offer.price_paise > max_budget:
                    over_by = offer.price_paise - max_budget
                    rejected_traces.append(RejectedOfferTrace(
                        offer_id=offer.offer_id,
                        merchant_id=offer.merchant_id,
                        rejection_reason=OfferRejectionCode.BUDGET_EXCEEDED,
                        detail=f"Offer price ₹{offer.price_paise / 100:.2f} exceeds buyer budget ₹{max_budget / 100:.2f} by ₹{over_by / 100:.2f}.",
                        expected_value=f"<= {max_budget} paise",
                        observed_value=f"{offer.price_paise} paise"
                    ))
                    step2_rejections.append(offer.offer_id)
                    continue

                surviving_step2.append(offer)

            eligible_offers = surviving_step2
            step_traces.append(DecisionStepTrace(
                step="BUDGET_FILTER",
                description="Filtered out offers exceeding stated budget ceiling or with currency mismatch",
                eligible_count_before=before_count,
                eligible_count_after=len(eligible_offers),
                rejections_in_step=step2_rejections
            ))

        # -------------------------------------------------------------
        # STEP 3: Hard Requirement Attribute Filters
        # -------------------------------------------------------------
        if intent.requirements:
            for req in intent.requirements:
                req_key = f"REQ_{req.attribute.upper()}_{req.operator.value}_{req.value}"
                hard_constraints_checked.append(req_key)
                before_count = len(eligible_offers)
                surviving_req: List[BuyerOffer] = []
                req_rejections: List[str] = []

                for offer in eligible_offers:
                    is_satisfied, fail_detail = self._check_requirement(req, offer)
                    if not is_satisfied:
                        rejected_traces.append(RejectedOfferTrace(
                            offer_id=offer.offer_id,
                            merchant_id=offer.merchant_id,
                            rejection_reason=OfferRejectionCode.HARD_REQUIREMENT_VIOLATED,
                            detail=fail_detail,
                            attribute_name=req.attribute,
                            expected_value=f"{req.operator.value} {req.value}",
                            observed_value=str(offer.relevant_attributes.get(req.attribute, "missing"))
                        ))
                        req_rejections.append(offer.offer_id)
                    else:
                        surviving_req.append(offer)

                eligible_offers = surviving_req
                step_traces.append(DecisionStepTrace(
                    step=f"REQUIREMENT_FILTER_{req.attribute.upper()}",
                    description=f"Filtered out offers violating hard requirement '{req.attribute}'",
                    eligible_count_before=before_count,
                    eligible_count_after=len(eligible_offers),
                    rejections_in_step=req_rejections
                ))

        # -------------------------------------------------------------
        # STEP 4: Explicit Buyer Exclusions Filter (Zero Tolerance)
        # -------------------------------------------------------------
        if intent.exclusions:
            for excl in intent.exclusions:
                excl_key = f"EXCL_{excl.attribute.upper()}_{excl.excluded_value.upper()}"
                hard_constraints_checked.append(excl_key)
                before_count = len(eligible_offers)
                surviving_excl: List[BuyerOffer] = []
                excl_rejections: List[str] = []

                for offer in eligible_offers:
                    is_excluded, excl_detail = self._check_exclusion(excl, offer)
                    if is_excluded:
                        rejected_traces.append(RejectedOfferTrace(
                            offer_id=offer.offer_id,
                            merchant_id=offer.merchant_id,
                            rejection_reason=OfferRejectionCode.EXCLUDED_BY_BUYER,
                            detail=excl_detail,
                            attribute_name=excl.attribute,
                            expected_value=f"NOT {excl.excluded_value}",
                            observed_value=excl.excluded_value
                        ))
                        excl_rejections.append(offer.offer_id)
                    else:
                        surviving_excl.append(offer)

                eligible_offers = surviving_excl
                step_traces.append(DecisionStepTrace(
                    step=f"EXCLUSION_FILTER_{excl.attribute.upper()}",
                    description=f"Filtered out offers containing buyer-excluded '{excl.excluded_value}'",
                    eligible_count_before=before_count,
                    eligible_count_after=len(eligible_offers),
                    rejections_in_step=excl_rejections
                ))

        return eligible_offers, rejected_traces, step_traces, hard_constraints_checked

    def _check_requirement(self, req: Any, offer: BuyerOffer) -> Tuple[bool, str]:
        """Check if an offer satisfies an AttributeRequirement."""
        attr_name = req.attribute
        target_val = req.value
        op = req.operator

        # Look in relevant_attributes
        attrs = offer.relevant_attributes
        if attr_name not in attrs:
            # Fallback: check if product_name contains the requirement
            if op == OperatorType.CONTAINS and str(target_val).lower() in offer.product_name.lower():
                return True, ""
            return False, f"Offer lacks mandatory attribute '{attr_name}'."

        actual_val = attrs[attr_name]

        # Handle numeric comparisons
        if op in (OperatorType.GTE, OperatorType.LTE):
            try:
                num_actual = float(actual_val)
                num_target = float(target_val)
                if op == OperatorType.GTE and num_actual >= num_target:
                    return True, ""
                elif op == OperatorType.LTE and num_actual <= num_target:
                    return True, ""
                return False, f"Attribute '{attr_name}' value {num_actual} does not satisfy {op.value} {num_target}."
            except (ValueError, TypeError):
                return False, f"Cannot perform numeric comparison on attribute '{attr_name}' with value '{actual_val}'."

        # Handle string equality / containment
        if op == OperatorType.EQ:
            if str(actual_val).strip().lower() == str(target_val).strip().lower():
                return True, ""
            return False, f"Attribute '{attr_name}' value '{actual_val}' does not equal '{target_val}'."

        if op == OperatorType.NEQ:
            if str(actual_val).strip().lower() != str(target_val).strip().lower():
                return True, ""
            return False, f"Attribute '{attr_name}' value '{actual_val}' must not equal '{target_val}'."

        if op == OperatorType.CONTAINS:
            if str(target_val).strip().lower() in str(actual_val).strip().lower():
                return True, ""
            return False, f"Attribute '{attr_name}' does not contain '{target_val}'."

        return False, f"Unsupported operator '{op}' for requirement '{attr_name}'."

    def _check_exclusion(self, excl: Any, offer: BuyerOffer) -> Tuple[bool, str]:
        """Check if an offer contains an excluded attribute value. Returns (is_excluded, detail)."""
        forbidden = excl.excluded_value.strip().lower()
        attr_name = excl.attribute.strip().lower()

        # 1. Check relevant_attributes
        for k, v in offer.relevant_attributes.items():
            if k.lower() == attr_name or forbidden in str(v).lower():
                if forbidden in str(v).lower():
                    return True, f"Offer attribute '{k}' contains excluded value '{forbidden}'."

        # 2. Check product_name
        if forbidden in offer.product_name.lower():
            return True, f"Product name '{offer.product_name}' contains excluded value '{forbidden}'."

        # 3. Check included_items
        for item in offer.included_items:
            if forbidden in item.lower():
                return True, f"Included accessory '{item}' contains excluded value '{forbidden}'."

        return False, ""
