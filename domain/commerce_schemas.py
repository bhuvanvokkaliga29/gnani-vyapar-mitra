"""Typed Pydantic Schemas for Merchant Commerce Operations & Agent Context."""

from decimal import Decimal
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

VALID_OBJECTIVES: Set[str] = {
    "BALANCE_REVENUE_AND_MARGIN",
    "MAXIMIZE_REVENUE",
    "MAXIMIZE_CONTRIBUTION",
    "INCREASE_AOV"
}

VALID_RELATIONSHIP_TYPES: Set[str] = {
    "COMPLEMENTARY",
    "SUBSTITUTE",
    "BUNDLE_COMPONENT",
    "UPSELL",
    "CROSS_SELL"
}

VALID_RELATIONSHIP_SOURCES: Set[str] = {
    "merchant_defined",
    "system_inferred"
}


class MerchantCreateRequest(BaseModel):
    id: str = Field(min_length=3, max_length=64, description="Merchant tenant ID (e.g. merch_atlas_travel)")
    name: str = Field(min_length=1, max_length=255, description="Merchant display name")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 3-letter currency")
    business_objective: str = Field(default="BALANCE_REVENUE_AND_MARGIN", description="Optimization goal")
    minimum_margin_percent: Decimal = Field(default=Decimal("25.00"), ge=0, le=100)
    maximum_discount_percent: Decimal = Field(default=Decimal("8.00"), ge=0, le=100)
    target_aov_paise: int = Field(default=400000, gt=0, description="Target AOV in integer paise")

    @field_validator("business_objective")
    @classmethod
    def validate_objective(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in VALID_OBJECTIVES:
            raise ValueError(f"Invalid business objective '{v}'. Must be one of: {sorted(VALID_OBJECTIVES)}")
        return v_upper

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()


class MerchantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    currency: str
    status: str
    business_objective: str
    minimum_margin_percent: Decimal
    maximum_discount_percent: Decimal
    target_aov_paise: int
    created_at: datetime
    updated_at: datetime


class ProductCreateRequest(BaseModel):
    id: str = Field(min_length=3, max_length=64, description="Product ID (e.g. prod_backpack)")
    sku: str = Field(min_length=1, max_length=64, description="Stock Keeping Unit")
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(min_length=1, max_length=64)
    price_paise: int = Field(gt=0, description="Retail price in integer paise")
    cost_paise: int = Field(ge=0, description="Unit COGS in integer paise")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    inventory_quantity: int = Field(default=0, ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def validate_inventory_bounds(self) -> 'ProductCreateRequest':
        if self.reserved_quantity > self.inventory_quantity:
            raise ValueError("Reserved quantity cannot exceed total inventory quantity")
        return self


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price_paise: Optional[int] = Field(default=None, gt=0)
    cost_paise: Optional[int] = Field(default=None, ge=0)
    inventory_quantity: Optional[int] = Field(default=None, ge=0)
    reserved_quantity: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_inventory_bounds(self) -> 'ProductUpdateRequest':
        if self.reserved_quantity is not None and self.inventory_quantity is not None:
            if self.reserved_quantity > self.inventory_quantity:
                raise ValueError("Reserved quantity cannot exceed total inventory quantity")
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    sku: str
    name: str
    description: Optional[str] = None
    category: str
    price_paise: int
    cost_paise: int
    currency: str
    inventory_quantity: int
    reserved_quantity: int
    available_to_sell: int
    gross_profit_paise: int
    gross_margin_percent: Decimal
    is_active: bool
    is_eligible: bool
    ineligibility_reason: Optional[str] = None
    attributes: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RelationshipCreateRequest(BaseModel):
    primary_product_id: str = Field(min_length=3, max_length=64)
    related_product_id: str = Field(min_length=3, max_length=64)
    relationship_type: str = Field(description="COMPLEMENTARY, SUBSTITUTE, BUNDLE_COMPONENT, UPSELL, CROSS_SELL")
    affinity_score: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
    source: str = Field(default="merchant_defined", description="'merchant_defined' or 'system_inferred'")
    confidence: Decimal = Field(default=Decimal("1.00"), ge=0, le=1)

    @field_validator("relationship_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type '{v}'. Must be one of: {sorted(VALID_RELATIONSHIP_TYPES)}")
        return v_upper

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in VALID_RELATIONSHIP_SOURCES:
            raise ValueError(f"Invalid source '{v}'. Must be one of: {sorted(VALID_RELATIONSHIP_SOURCES)}")
        return v_lower


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_id: str
    primary_product_id: str
    related_product_id: str
    relationship_type: str
    affinity_score: Decimal
    source: str
    confidence: Decimal
    created_at: datetime


class ConstraintsUpdateRequest(BaseModel):
    minimum_margin_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    maximum_discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    target_aov_paise: Optional[int] = Field(default=None, gt=0)
    business_objective: Optional[str] = None

    @field_validator("business_objective")
    @classmethod
    def validate_objective(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_upper = v.upper()
        if v_upper not in VALID_OBJECTIVES:
            raise ValueError(f"Invalid business objective '{v}'. Must be one of: {sorted(VALID_OBJECTIVES)}")
        return v_upper


class PrioritiesUpdateRequest(BaseModel):
    priority_product_ids: List[str] = Field(default_factory=list)
    priority_categories: List[str] = Field(default_factory=list)
    clearance_product_ids: List[str] = Field(default_factory=list)


class PrioritiesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_id: str
    priority_product_ids: List[str]
    priority_categories: List[str]
    clearance_product_ids: List[str]
    updated_at: datetime


# =============================================================================
# THE UNIFIED COMMERCE CONTEXT CONSUMED BY FUTURE POLICY AGENT
# =============================================================================

class MerchantCommerceContext(BaseModel):
    """The single deterministic knowledge layer consumed by the future Policy Agent.

    Contains all facts required for commercial reasoning:
    - Merchant objectives & targets
    - Financial guardrail constraints
    - Full catalog with computed unit economics & stock eligibility
    - Known product affinity & substitute relationships
    - Inventory priorities and clearance targets
    """
    merchant_id: str
    merchant_name: str
    currency: str
    status: str
    business_objective: str
    constraints: Dict[str, Any]
    priorities: Dict[str, Any]
    products: List[ProductResponse]
    relationships: List[RelationshipResponse]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
