"""Pydantic v2 schemas for AI Buyer Lab (Contract: buyer-selection/v1).

The AI Buyer Lab evaluates candidate offers from a machine-buyer's perspective.
Inviolable Invariant: The buyer has ZERO visibility into merchant internal economics
(no COGS, no internal margins, no internal merchant objectives, no internal policy scores).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator
from domain.intent_schemas import BuyerIntent


class BuyerPersonaType(str, Enum):
    """Behavioral test configuration for simulated machine-buyers.

    NOTE: These are behavioral evaluation profiles, NOT claims about human demographics or psychology.
    """
    BALANCED = "BALANCED"
    STRICT_REQUIREMENTS = "STRICT_REQUIREMENTS"
    PRICE_SENSITIVE = "PRICE_SENSITIVE"
    FEATURE_PRIORITY = "FEATURE_PRIORITY"
    WARRANTY_SERVICE = "WARRANTY_SERVICE"
    BUNDLE_VALUE = "BUNDLE_VALUE"


class OfferRejectionCode(str, Enum):
    """Machine-readable rejection taxonomy for offers failing buyer criteria."""
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNAVAILABLE = "UNAVAILABLE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    HARD_REQUIREMENT_VIOLATED = "HARD_REQUIREMENT_VIOLATED"
    EXCLUDED_BY_BUYER = "EXCLUDED_BY_BUYER"
    MALFORMED_OFFER = "MALFORMED_OFFER"


class SelectionTaxonomy(str, Enum):
    """Reason categories for why an offer was selected by the machine-buyer."""
    HARD_REQUIREMENT_MATCH = "HARD_REQUIREMENT_MATCH"
    BUDGET_MATCH = "BUDGET_MATCH"
    PREFERENCE_MATCH = "PREFERENCE_MATCH"
    TOTAL_VALUE_MATCH = "TOTAL_VALUE_MATCH"
    BUNDLE_VALUE = "BUNDLE_VALUE"
    SERVICE_VALUE = "SERVICE_VALUE"
    WARRANTY_VALUE = "WARRANTY_VALUE"
    DELIVERY_VALUE = "DELIVERY_VALUE"
    LOWER_PRICE_AMONG_ELIGIBLE = "LOWER_PRICE_AMONG_ELIGIBLE"
    DETERMINISTIC_TIE_BREAK = "DETERMINISTIC_TIE_BREAK"
    NO_ELIGIBLE_OFFER = "NO_ELIGIBLE_OFFER"


class BuyerOffer(BaseModel):
    """Normalized, buyer-visible representation of a commercial offer.

    CRITICAL SECURITY INVARIANT:
    Contains ONLY buyer-visible attributes. Forbids internal merchant financial metadata:
    - NO cogs_paise
    - NO margin_percent
    - NO merchant_objective
    - NO policy_ranking_score
    - NO execution_authorization
    """
    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(min_length=1, max_length=64, description="Unique identifier for the offer")
    merchant_id: str = Field(min_length=1, max_length=64, description="Merchant identifier")
    merchant_label: str = Field(min_length=1, max_length=128, description="Public merchant brand name")
    product_id: str = Field(min_length=1, max_length=64, description="Primary product identifier")
    product_name: str = Field(min_length=1, max_length=256, description="Buyer-visible product name")
    category: Optional[str] = Field(default=None, max_length=64, description="Product category")
    price_paise: int = Field(ge=0, description="Buyer-visible total price in integer paise")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="Currency ISO code")
    availability: bool = Field(default=True, description="Whether product is currently available to purchase")
    relevant_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Buyer-visible physical specifications (e.g. laptop_size, weight_kg, material, color)"
    )
    included_items: List[str] = Field(
        default_factory=list,
        description="Items/accessories included in bundle or package"
    )
    warranty_months: int = Field(default=12, ge=0, description="Manufacturer or merchant warranty in months")
    delivery_days: int = Field(default=3, ge=0, description="Estimated delivery turnaround in business days")
    service_information: Optional[str] = Field(default=None, max_length=256, description="Post-purchase service details")
    incentives: List[str] = Field(
        default_factory=list,
        description="Buyer-visible perks (e.g. free_shipping, complimentary_pouch)"
    )
    provenance: Optional[str] = Field(default=None, max_length=128, description="Origin tracking identifier")
    is_synthetic: bool = Field(default=False, description="True if synthetic competitor fixture for benchmark")


class RejectedOfferTrace(BaseModel):
    """Detailed audit trace explaining why a candidate offer was deemed ineligible."""
    model_config = ConfigDict(extra="forbid")

    offer_id: str
    merchant_id: str
    rejection_reason: OfferRejectionCode
    detail: str
    attribute_name: Optional[str] = None
    expected_value: Optional[str] = None
    observed_value: Optional[str] = None


class DecisionStepTrace(BaseModel):
    """Step-by-step audit record of the buyer decision process."""
    model_config = ConfigDict(extra="forbid")

    step: str
    description: str
    eligible_count_before: int
    eligible_count_after: int
    rejections_in_step: List[str] = Field(default_factory=list)


class BuyerSelectionResult(BaseModel):
    """Structured machine-readable result of simulated buyer evaluation.

    Contract: buyer-selection/v1
    """
    model_config = ConfigDict(extra="forbid")

    result_version: str = Field(default="buyer-selection/v1", description="Contract schema version")
    buyer_intent_version: str = Field(default="buyer-intent/v1", description="Version of BuyerIntent evaluated")
    simulation_version: str = Field(default="buyer-sim/v1", description="Simulation engine version")
    scenario_id: Optional[str] = Field(default=None, description="Benchmark scenario identifier if applicable")
    selected_offer_id: Optional[str] = Field(
        default=None,
        description="Winning offer ID, or None if NO_ELIGIBLE_OFFER"
    )
    selected_offer: Optional[BuyerOffer] = Field(
        default=None,
        description="Full buyer-visible offer object of winner, or None"
    )
    candidate_offer_ids: List[str] = Field(default_factory=list, description="All offers submitted to evaluation")
    eligible_offer_ids: List[str] = Field(default_factory=list, description="Offers passing all hard constraints")
    rejected_offers: List[RejectedOfferTrace] = Field(default_factory=list, description="Audit trace of ineligible offers")
    selection_reasons: List[SelectionTaxonomy] = Field(default_factory=list, description="Categorized selection reasons")
    selection_rationale: str = Field(description="Evidence-grounded rationale explaining the selection")
    satisfied_preferences: List[str] = Field(default_factory=list, description="Soft preferences met by winner")
    unmet_preferences: List[str] = Field(default_factory=list, description="Soft preferences not met by winner")
    hard_constraints_checked: List[str] = Field(default_factory=list, description="Hard constraints evaluated")
    decision_trace: List[DecisionStepTrace] = Field(default_factory=list, description="Chronological filtering trace")
    buyer_persona: BuyerPersonaType = Field(default=BuyerPersonaType.BALANCED)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_selection_consistency(self) -> 'BuyerSelectionResult':
        if self.selected_offer_id is None:
            if SelectionTaxonomy.NO_ELIGIBLE_OFFER not in self.selection_reasons:
                self.selection_reasons.append(SelectionTaxonomy.NO_ELIGIBLE_OFFER)
        else:
            if self.selected_offer_id not in self.eligible_offer_ids:
                raise ValueError("Selected offer must be member of eligible_offer_ids")
            if self.selected_offer and self.selected_offer.offer_id != self.selected_offer_id:
                raise ValueError("selected_offer.offer_id must match selected_offer_id")
        return self


class BuyerSimulationRequest(BaseModel):
    """API request payload for POST /api/v1/buyer-lab/simulate."""
    model_config = ConfigDict(extra="forbid")

    intent: BuyerIntent = Field(description="Structured BuyerIntent v1")
    offers: List[BuyerOffer] = Field(min_length=0, max_length=20, description="List of candidate offers to evaluate")
    scenario_id: Optional[str] = Field(default=None, max_length=64, description="Optional benchmark scenario ID")
    buyer_persona: BuyerPersonaType = Field(default=BuyerPersonaType.BALANCED, description="Behavioral evaluation persona")


class BuyerSimulationResponse(BaseModel):
    """API response payload for POST /api/v1/buyer-lab/simulate."""
    model_config = ConfigDict(extra="forbid")

    result: BuyerSelectionResult
    simulation_id: str
    execution_time_ms: float
