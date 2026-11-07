"""Typed Pydantic Schemas for Merchant Policy Agent & Commercial Strategies.

Defines the inviolable Phase 4 data contracts.
Enforces extra="forbid" on all structures. Zero floating-point money.
"""

from enum import Enum
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from domain.intent_schemas import BuyerIntent, ConfidenceLevel
from domain.commerce_schemas import MerchantCommerceContext


class StrategyType(str, Enum):
    SINGLE_PRODUCT = "SINGLE_PRODUCT"
    COMPLEMENTARY_BUNDLE = "COMPLEMENTARY_BUNDLE"
    VALUE_BUNDLE = "VALUE_BUNDLE"
    ALTERNATIVE_PRODUCT = "ALTERNATIVE_PRODUCT"
    NON_PRICE_INCENTIVE = "NON_PRICE_INCENTIVE"
    BOUNDED_DISCOUNT = "BOUNDED_DISCOUNT"
    NO_OFFER = "NO_OFFER"


class ProposalStatus(str, Enum):
    """Proposal status taxonomy.

    SEMANTIC BOUNDARY FREEZE:
    - VALID: Proposal passed Phase 4 deterministic validation (or valid NO_OFFER fallback).
    - APPROVED_FOR_EVALUATION: Proposal passed Phase 4 validation and is eligible to be evaluated
      in a future experiment (e.g. AI Buyer Lab). It does NOT mean approved for financial execution.
    - REJECTED: Candidate validation failed without safe fallback.
    - CLARIFICATION_REQUIRED: Unresolved intent conflicts or missing dimensions require buyer clarification.
    - NOTE: EXECUTION_APPROVED is strictly reserved for Phase 5+ Deterministic Commercial Execution Gate revalidation
      and is forbidden in Phase 4.
    """
    GENERATED = "GENERATED"
    VALID = "VALID"
    REJECTED = "REJECTED"
    APPROVED_FOR_EVALUATION = "APPROVED_FOR_EVALUATION"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


class CandidateValidationStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RejectionReason(str, Enum):
    MARGIN_TOO_LOW = "MARGIN_TOO_LOW"
    DISCOUNT_TOO_HIGH = "DISCOUNT_TOO_HIGH"
    OVER_BUDGET = "OVER_BUDGET"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    EXCLUDED_BY_BUYER = "EXCLUDED_BY_BUYER"
    INACTIVE_PRODUCT = "INACTIVE_PRODUCT"
    INVALID_RELATIONSHIP = "INVALID_RELATIONSHIP"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    REQUIREMENT_NOT_MET = "REQUIREMENT_NOT_MET"
    UNKNOWN_REQUIRED_INFORMATION = "UNKNOWN_REQUIRED_INFORMATION"
    CROSS_MERCHANT_PRODUCT = "CROSS_MERCHANT_PRODUCT"
    ZERO_ITEMS = "ZERO_ITEMS"


VALID_EVIDENCE_TYPES = {
    "buyer_requirement",
    "merchant_attribute",
    "merchant_relationship",
    "deterministic_economics",
    "deterministic_validation"
}


class PolicyEvidence(BaseModel):
    """Verifiable link between proposed candidate and structured input facts."""
    model_config = ConfigDict(extra="forbid")

    evidence_type: str = Field(description="buyer_requirement, merchant_attribute, merchant_relationship, deterministic_economics, or deterministic_validation")
    field: str = Field(description="The attribute or relationship referenced")
    description: str = Field(description="Concrete grounding statement")

    @field_validator("evidence_type")
    @classmethod
    def validate_evidence_type(cls, v: str) -> str:
        if v not in VALID_EVIDENCE_TYPES:
            raise ValueError(f"Invalid evidence_type '{v}'. Must be one of: {sorted(VALID_EVIDENCE_TYPES)}")
        return v


class IncentiveProposal(BaseModel):
    """Proposed commercial incentive subject to deterministic guardrails."""
    model_config = ConfigDict(extra="forbid")

    incentive_type: str = Field(description="discount, non_price, free_shipping, or bundled_addon")
    discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100, description="Proposed discount percentage")
    description: Optional[str] = Field(default=None, description="Human-readable description of incentive")


class CandidateEconomics(BaseModel):
    """Exact computed financial figures for a proposed strategy in integer paise."""
    model_config = ConfigDict(extra="forbid")

    gross_revenue_paise: int = Field(ge=0, description="Baseline retail price of all basket items in paise")
    promotional_discount_paise: int = Field(default=0, ge=0, description="Promotional discount in paise")
    net_revenue_paise: int = Field(ge=0, description="Customer payable amount before execution in paise")
    total_cogs_paise: int = Field(ge=0, description="Sum of unit costs in paise")
    gross_profit_paise: int = Field(description="net_revenue - total_cogs in paise")
    gross_margin_percent: Decimal = Field(description="Exact gross margin percentage")
    effective_discount_percent: Decimal = Field(default=Decimal("0.00"), description="Discount as percentage of baseline")
    is_compliant: bool = Field(description="True if both margin floor and discount ceiling are satisfied")


class PolicyScore(BaseModel):
    """Transparent multi-factor ranking score for strategy prioritization.

    CRITICAL SEMANTIC GUARANTEE:
    This score is an internal policy ranking metric.
    It is NOT a probability of conversion, probability of purchase, or guaranteed revenue forecast.
    """
    model_config = ConfigDict(extra="forbid")

    buyer_fit_score: float = Field(ge=0.0, le=1.0, description="Semantic fit to buyer requirements & preferences (ranking metric, NOT conversion probability)")
    economic_value_score: float = Field(ge=0.0, le=1.0, description="Contribution toward merchant target AOV / revenue (ranking metric, NOT conversion probability)")
    objective_alignment_score: float = Field(ge=0.0, le=1.0, description="Alignment with active merchant objective (ranking metric, NOT conversion probability)")
    constraint_safety_score: float = Field(ge=0.0, le=1.0, description="Proximity to guardrail thresholds (ranking metric, NOT conversion probability)")
    composite_score: float = Field(ge=0.0, le=1.0, description="Transparent weighted composite candidate ranking score (ranking metric, NOT conversion probability)")


class PolicyCandidate(BaseModel):
    """An individual candidate commercial strategy proposed by the Policy Agent."""
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(description="Unique candidate identifier")
    strategy_type: StrategyType = Field(description="Strategy taxonomy classification")
    product_ids: List[str] = Field(min_length=0, description="Proposed product IDs")
    bundle_components: List[Dict[str, Any]] = Field(default_factory=list, description="Component breakdown with quantities")
    incentive: Optional[IncentiveProposal] = Field(default=None, description="Proposed commercial incentive")
    positioning: Optional[str] = Field(default=None, description="Commercial framing / value proposition")
    rationale: str = Field(description="Explainable rationale grounded in merchant and buyer context")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Reasoning confidence")
    evidence: List[PolicyEvidence] = Field(default_factory=list, description="Grounding evidence traces")
    deterministic_economics: Optional[CandidateEconomics] = Field(default=None, description="Calculated economics")
    validation_status: CandidateValidationStatus = Field(default=CandidateValidationStatus.REJECTED)
    rejection_reasons: List[str] = Field(default_factory=list, description="Machine-readable rejection codes")
    score: Optional[PolicyScore] = Field(default=None, description="Multi-factor ranking score")


class PolicyProposal(BaseModel):
    """The authoritative versioned commercial strategy output from the Policy Agent.

    The LLM proposes candidates; the deterministic validator evaluates compliance.
    This proposal feeds downstream execution gates. It CANNOT execute transactions.

    PROVENANCE & SNAPSHOT NOTICE:
    This proposal represents an advisory recommendation based on the MerchantCommerceContext
    snapshot available at generation time. It must be revalidated against fresh deterministic
    merchant state before any execution in Phase 5.
    """
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(description="Unique proposal identifier")
    buyer_intent_id: Optional[str] = Field(default=None, description="Associated buyer intent ID")
    merchant_id: str = Field(description="Merchant tenant ID")
    policy_version: str = Field(default="merchant-policy/v1", description="Policy schema version")
    prompt_version: str = Field(default="merchant-policy-agent/v1", description="System prompt version")
    intent_version: str = Field(default="buyer-intent/v1", description="BuyerIntent schema contract version")
    context_version: str = Field(default="commerce-context/v1", description="MerchantCommerceContext version")
    validator_version: str = Field(default="deterministic-validator/v1", description="Deterministic validator version")
    objective: str = Field(default="BALANCE_REVENUE_AND_MARGIN", description="Active merchant commercial objective")
    model_provider: str = Field(default="deterministic-reasoning-engine", description="Model provider")
    model_name: str = Field(default="merchant-policy-agent/v1", description="Model identifier")
    status: ProposalStatus = Field(description="Overall proposal status")
    candidates: List[PolicyCandidate] = Field(default_factory=list, description="Bounded set of evaluated candidates")
    selected_candidate: Optional[PolicyCandidate] = Field(default=None, description="Top-ranked compliant candidate (or NO_OFFER fallback)")
    total_candidates: int = Field(default=0, ge=0)
    valid_candidates_count: int = Field(default=0, ge=0)
    rejected_candidates_count: int = Field(default=0, ge=0)
    is_provisional: bool = Field(default=True, description="Provisional proposal based on context snapshot; requires revalidation before execution")
    context_snapshot_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the merchant commerce context snapshot")
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Exact timestamp proposal was generated")
    audit_trail: Dict[str, Any] = Field(default_factory=dict, description="Execution and evaluation audit trace")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# API REQUEST & RESPONSE DTOs
# =============================================================================

class PolicyGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=3, max_length=64, description="Merchant tenant ID")
    intent: BuyerIntent = Field(description="Validated BuyerIntent v1")
    commerce_context: Optional[MerchantCommerceContext] = Field(
        default=None,
        description="Optional in-memory context; fetched from DB if omitted"
    )


class PolicyGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: PolicyProposal
    latency_ms: float
    audit_run_id: str
