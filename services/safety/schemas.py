"""Pydantic Schemas and Contracts for Deterministic Policy Safety & Admissibility Gate.

Contract Version: policy-safety/v1
Defines:
- Strict machine-readable failure codes with canonical priority hierarchy.
- PolicySafetyStatus enum (ADMISSIBLE, REJECTED).
- PolicySafetyRequest and PolicySafetyResult DTOs.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from domain.intent_schemas import BuyerIntent
from services.policy.schemas import PolicyCandidate, CandidateEconomics

SAFETY_SCHEMA_VERSION = "policy-safety/v1"


class PolicySafetyStatus(str, Enum):
    """Deterministic outcome of Phase 8.6 safety and admissibility evaluation."""
    ADMISSIBLE = "ADMISSIBLE"
    REJECTED = "REJECTED"


class PolicySafetyFailureCode(str, Enum):
    """Machine-readable safety failure codes.
    
    Ordered by strict canonical domain priority.
    """
    MERCHANT_SCOPE_MISMATCH = "MERCHANT_SCOPE_MISMATCH"
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    INVALID_POLICY = "INVALID_POLICY"
    POLICY_VERSION_INVALID = "POLICY_VERSION_INVALID"
    VERSION_INCOMPATIBLE = "VERSION_INCOMPATIBLE"
    STALE_CONTEXT = "STALE_CONTEXT"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_INELIGIBLE = "PRODUCT_INELIGIBLE"
    RELATIONSHIP_INVALID = "RELATIONSHIP_INVALID"
    INVENTORY_INSUFFICIENT = "INVENTORY_INSUFFICIENT"
    DISCOUNT_LIMIT_EXCEEDED = "DISCOUNT_LIMIT_EXCEEDED"
    CONTRIBUTION_FLOOR_VIOLATED = "CONTRIBUTION_FLOOR_VIOLATED"
    BUDGET_LIMIT_EXCEEDED = "BUDGET_LIMIT_EXCEEDED"
    ECONOMICS_RECALCULATION_FAILED = "ECONOMICS_RECALCULATION_FAILED"


# Deterministic priority ranking for multiple simultaneous failure codes
FAILURE_CODE_PRIORITY: Dict[PolicySafetyFailureCode, int] = {
    PolicySafetyFailureCode.MERCHANT_SCOPE_MISMATCH: 1,
    PolicySafetyFailureCode.POLICY_NOT_FOUND: 2,
    PolicySafetyFailureCode.INVALID_POLICY: 3,
    PolicySafetyFailureCode.POLICY_VERSION_INVALID: 4,
    PolicySafetyFailureCode.VERSION_INCOMPATIBLE: 5,
    PolicySafetyFailureCode.STALE_CONTEXT: 6,
    PolicySafetyFailureCode.PRODUCT_NOT_FOUND: 7,
    PolicySafetyFailureCode.PRODUCT_INELIGIBLE: 8,
    PolicySafetyFailureCode.RELATIONSHIP_INVALID: 9,
    PolicySafetyFailureCode.INVENTORY_INSUFFICIENT: 10,
    PolicySafetyFailureCode.DISCOUNT_LIMIT_EXCEEDED: 11,
    PolicySafetyFailureCode.CONTRIBUTION_FLOOR_VIOLATED: 12,
    PolicySafetyFailureCode.BUDGET_LIMIT_EXCEEDED: 13,
    PolicySafetyFailureCode.ECONOMICS_RECALCULATION_FAILED: 14,
}


class PolicySafetyRequest(BaseModel):
    """Input payload to evaluate admissibility of a proposed commercial policy.
    
    Accepts ONE candidate policy proposal for safety validation.
    """
    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(description="Authoritative merchant identifier")
    opportunity_id: str = Field(description="Canonical decision instance identifier")
    buyer_context_key: str = Field(description="Pre-decision buyer context identifier")
    proposed_policy: PolicyCandidate = Field(description="Single proposed candidate policy")
    proposed_policy_version: str = Field(default="merchant-policy/v1", description="Proposed policy version")
    selection_id: Optional[str] = Field(default=None, description="Optional Phase 8.5 selection record reference")
    source_decision_version: str = Field(default="policy-selection/v1", description="Source selection contract version")
    safety_version: str = Field(default=SAFETY_SCHEMA_VERSION, description="Target safety contract version")
    intent: Optional[BuyerIntent] = Field(default=None, description="Buyer intent containing preferences/exclusions/budget")
    context_snapshot_id: Optional[str] = Field(default=None, description="Optional caller context snapshot identifier")


class PolicySafetyResult(BaseModel):
    """Authoritative outcome of Phase 8.6 safety and admissibility validation."""
    model_config = ConfigDict(extra="forbid")

    safety_check_id: str = Field(description="Unique safety check identifier (safe_...)")
    merchant_id: str = Field(description="Validated merchant identifier")
    opportunity_id: str = Field(description="Canonical opportunity identifier")
    policy_id: str = Field(description="Candidate policy identifier evaluated")
    policy_version: str = Field(description="Candidate policy version")
    status: PolicySafetyStatus = Field(description="ADMISSIBLE or REJECTED")
    failure_codes: List[PolicySafetyFailureCode] = Field(default_factory=list, description="Sorted deterministic failure codes")
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of validation")
    merchant_context_version: Optional[str] = Field(default=None, description="Version/timestamp of fresh merchant context used")
    recalculated_economics: Optional[CandidateEconomics] = Field(default=None, description="Economics recomputed against fresh DB state")
    policy_safety_version: str = Field(default=SAFETY_SCHEMA_VERSION, description="Contract version")
    validation_reason: str = Field(description="Deterministic machine-readable summary reason")
