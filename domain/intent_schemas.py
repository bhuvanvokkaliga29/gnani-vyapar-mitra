"""Typed Pydantic Models for BuyerIntent Machine-Readable Contract."""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


class BudgetType(str, Enum):
    MAX = "MAX"
    RANGE = "RANGE"
    TARGET = "TARGET"
    APPROXIMATE = "APPROXIMATE"


class ConstraintType(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class OperatorType(str, Enum):
    GTE = "GTE"
    LTE = "LTE"
    EQ = "EQ"
    NEQ = "NEQ"
    CONTAINS = "CONTAINS"


class PreferenceStrength(str, Enum):
    EXPLICIT = "explicit"
    PREFERRED = "preferred"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BudgetConstraint(BaseModel):
    """Monetary constraint extracted from buyer input, stored in integer paise."""
    model_config = ConfigDict(extra="forbid")

    amount_paise: Optional[int] = Field(default=None, ge=0, description="Target or approximate budget in paise")
    min_amount_paise: Optional[int] = Field(default=None, ge=0, description="Lower bound for range in paise")
    max_amount_paise: Optional[int] = Field(default=None, ge=0, description="Upper bound for range or ceiling in paise")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    budget_type: BudgetType = Field(default=BudgetType.MAX)
    constraint_type: ConstraintType = Field(default=ConstraintType.HARD)

    @model_validator(mode="after")
    def validate_budget_bounds(self) -> 'BudgetConstraint':
        if self.min_amount_paise is not None and self.max_amount_paise is not None:
            if self.min_amount_paise > self.max_amount_paise:
                raise ValueError("min_amount_paise cannot be greater than max_amount_paise")
        return self


class AttributeRequirement(BaseModel):
    """Explicit HARD requirement that candidate products must satisfy."""
    model_config = ConfigDict(extra="forbid")

    attribute: str = Field(min_length=1, max_length=64, description="Attribute name (e.g. laptop_size)")
    operator: OperatorType = Field(default=OperatorType.GTE)
    value: Any = Field(description="Attribute target value (e.g. 15.0, True)")
    unit: Optional[str] = Field(default=None, max_length=32, description="Physical unit (e.g. inch, liters)")
    importance: str = Field(default="required")


class AttributePreference(BaseModel):
    """Explicit SOFT preference (nice-to-have) that guides product ranking."""
    model_config = ConfigDict(extra="forbid")

    attribute: str = Field(min_length=1, max_length=64, description="Attribute name (e.g. weight, color)")
    preference: str = Field(min_length=1, max_length=128, description="Desired quality (e.g. lightweight, black)")
    strength: PreferenceStrength = Field(default=PreferenceStrength.PREFERRED)


class ExclusionConstraint(BaseModel):
    """Negative constraint explicitly forbidding a material, color, or property."""
    model_config = ConfigDict(extra="forbid")

    attribute: str = Field(min_length=1, max_length=64, description="Attribute name (e.g. material, color)")
    excluded_value: str = Field(min_length=1, max_length=128, description="Forbidden value (e.g. leather, red)")
    importance: str = Field(default="required")


class TemporalConstraint(BaseModel):
    """Requested delivery date or usage timeframe."""
    model_config = ConfigDict(extra="forbid")

    delivery_deadline: Optional[str] = Field(default=None, description="Stated deadline (e.g. Friday, tomorrow)")
    usage_date: Optional[str] = Field(default=None, description="Target event date (e.g. flight next week)")


class IntentConflict(BaseModel):
    """Contradiction detected between user utterances or incompatible constraints."""
    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Field where conflict occurred (e.g. budget, category)")
    previous_value: Any = Field(description="Prior value stated by user")
    new_value: Any = Field(description="Conflicting new value stated by user")
    reason: str = Field(description="Explanation of the contradiction")


class IntentEvidence(BaseModel):
    """Verifiable text span supporting an extracted intent field."""
    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Extracted field name")
    source_text: str = Field(description="Direct verbatim phrase from buyer message")


class BuyerIntent(BaseModel):
    """Strict machine-readable representation of extracted buyer requirements and constraints.

    The future Policy Agent reasons over this object paired with MerchantCommerceContext.
    Does NOT contain product recommendations, offers, or commercial decisions.
    """
    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = Field(default=None, description="Normalized item category or None if ambiguous")
    use_case: Optional[str] = Field(default=None, description="Explicitly stated use-case (e.g. business_travel)")
    quantity: Optional[int] = Field(default=None, ge=1, description="Explicitly requested quantity or None")
    budget: Optional[BudgetConstraint] = Field(default=None, description="Budget constraint")
    requirements: List[AttributeRequirement] = Field(default_factory=list, description="Hard requirements")
    preferences: List[AttributePreference] = Field(default_factory=list, description="Soft preferences")
    exclusions: List[ExclusionConstraint] = Field(default_factory=list, description="Explicit exclusions/negations")
    temporal: Optional[TemporalConstraint] = Field(default=None, description="Temporal delivery/usage constraint")
    unknowns: List[str] = Field(default_factory=list, description="Critical dimensions buyer did not specify")
    conflicts: List[IntentConflict] = Field(default_factory=list, description="Detected contradictions")
    needs_clarification: bool = Field(default=False, description="True if contradictions or ambiguity require resolution")
    clarification_questions: List[str] = Field(default_factory=list, description="Proposed clarification questions")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Extraction certainty")
    evidence: List[IntentEvidence] = Field(default_factory=list, description="Audit evidence traces")
    schema_version: str = Field(default="buyer-intent/v1", description="Contract schema version")
    prompt_version: str = Field(default="intent-extractor/v1", description="System prompt version")


# =============================================================================
# API REQUEST & RESPONSE DTOs
# =============================================================================

class IntentParseRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="Raw buyer message")
    conversation_id: Optional[str] = Field(default=None, description="Session ID for multi-turn conversational memory")


class IntentParseResponse(BaseModel):
    intent: BuyerIntent
    conversation_id: str
    turn_index: int
    processing_time_ms: float
