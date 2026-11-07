"""AI Buyer Lab: Controlled Machine-Buyer Simulation & Offer Selection Environment.

Phase 6 of Merchant Policy Agent (Razorpay AI Buildathon 2026 - Track 01).
Contract: buyer-selection/v1
"""

from services.buyer_lab.schemas import (
    BuyerOffer,
    BuyerSelectionResult,
    BuyerPersonaType,
    OfferRejectionCode,
    SelectionTaxonomy,
    RejectedOfferTrace,
    DecisionStepTrace,
    BuyerSimulationRequest,
    BuyerSimulationResponse
)
from services.buyer_lab.errors import (
    BuyerLabError,
    IneligibleOfferError,
    MalformedOfferError,
    SecurityBoundaryViolationError
)
from services.buyer_lab.filter import EligibilityFilter
from services.buyer_lab.evaluator import PreferenceEvaluator
from services.buyer_lab.simulator import BuyerSimulator
from services.buyer_lab.competitors import get_synthetic_competitor_offers
from services.buyer_lab.benchmark import BenchmarkScenario, get_all_benchmark_scenarios

__all__ = [
    "BuyerOffer",
    "BuyerSelectionResult",
    "BuyerPersonaType",
    "OfferRejectionCode",
    "SelectionTaxonomy",
    "RejectedOfferTrace",
    "DecisionStepTrace",
    "BuyerSimulationRequest",
    "BuyerSimulationResponse",
    "BuyerLabError",
    "IneligibleOfferError",
    "MalformedOfferError",
    "SecurityBoundaryViolationError",
    "EligibilityFilter",
    "PreferenceEvaluator",
    "BuyerSimulator",
    "get_synthetic_competitor_offers",
    "BenchmarkScenario",
    "get_all_benchmark_scenarios"
]
