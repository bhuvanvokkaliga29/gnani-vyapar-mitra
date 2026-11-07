"""Strongly-typed schemas and data transfer objects for the MCP interface.

Contract: mcp-commerce/v1

INVARIANTS:
1. Every buyer-facing schema has model_config = ConfigDict(extra="forbid").
2. Zero leakage of internal merchant unit economics (cost_paise, COGS, margin percent,
   predicted contribution, LinUCB weights, uncertainty, or safety audit traces).
3. All prices are represented in integer paise.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class McpCapability(str, Enum):
    """Granular permissions that can be granted to an external AI buyer agent."""
    CATALOG_READ = "CATALOG_READ"
    INTENT_EVALUATE = "INTENT_EVALUATE"
    OFFER_READ = "OFFER_READ"
    CHECKOUT_REQUEST = "CHECKOUT_REQUEST"
    ORDER_STATUS_READ = "ORDER_STATUS_READ"


ALL_MCP_CAPABILITIES: Set[McpCapability] = {
    McpCapability.CATALOG_READ,
    McpCapability.INTENT_EVALUATE,
    McpCapability.OFFER_READ,
    McpCapability.CHECKOUT_REQUEST,
    McpCapability.ORDER_STATUS_READ,
}

READ_ONLY_CAPABILITIES: Set[McpCapability] = {
    McpCapability.CATALOG_READ,
    McpCapability.INTENT_EVALUATE,
    McpCapability.OFFER_READ,
    McpCapability.ORDER_STATUS_READ,
}


class BuyerAgentIdentity(BaseModel):
    """Authenticated identity of the external AI buyer agent."""
    model_config = ConfigDict(extra="forbid")

    buyer_agent_id: str = Field(..., description="Unique client identifier for the external AI buyer")
    client_name: str = Field(default="generic_ai_buyer", description="Client framework or agent name")
    client_version: str = Field(default="1.0.0", description="Client version")
    merchant_id: str = Field(..., description="Authoritative merchant tenant scope bound to credentials")
    granted_capabilities: Set[McpCapability] = Field(
        default_factory=lambda: set(ALL_MCP_CAPABILITIES),
        description="Explicit capabilities granted to this agent"
    )


class BuyerSafeProductView(BaseModel):
    """Authoritative, sanitized buyer view of a catalog product.
    
    FIREWALL INVARIANT:
    Zero cost_paise, COGS, or margin fields are present.
    """
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Authoritative product identifier (e.g. prod_...)")
    sku: str = Field(..., description="Stock keeping unit")
    name: str = Field(..., description="Product title")
    description: Optional[str] = Field(default=None, description="Buyer-visible product description")
    category: str = Field(..., description="Product category taxonomy")
    price_paise: int = Field(ge=0, description="Customer selling price in integer paise")
    currency: str = Field(default="INR", description="Three-letter currency code")
    in_stock: bool = Field(..., description="Whether available inventory > 0")
    available_quantity: int = Field(ge=0, description="Available to sell quantity")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Buyer-visible attributes")


class BuyerSafeIntentResponse(BaseModel):
    """Normalized structured intent extracted from buyer natural language.
    
    Derived via Phase 3 IntentExtractor with zero prompt injection bypass.
    """
    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = Field(default=None, description="Target product category")
    use_case: Optional[str] = Field(default=None, description="Identified use case")
    budget_paise: Optional[int] = Field(default=None, ge=0, description="Extracted maximum budget in paise")
    quantity: int = Field(default=1, ge=1, description="Requested quantity")
    requirements: List[str] = Field(default_factory=list, description="Hard buyer constraints")
    preferences: List[str] = Field(default_factory=list, description="Soft buyer preferences")
    exclusions: List[str] = Field(default_factory=list, description="Explicit exclusions")
    confidence: str = Field(default="HIGH", description="Extraction confidence")
    prompt_injection_neutralized: bool = Field(
        default=False,
        description="True if adversarial instruction patterns were detected and neutralized"
    )


class BuyerOfferItem(BaseModel):
    """Item included in a commercial offer."""
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    quantity: int = Field(default=1, ge=1, description="Item quantity in bundle/offer")
    unit_price_paise: int = Field(ge=0, description="Item selling price in paise")


class BuyerSafeOfferView(BaseModel):
    """Authoritative, buyer-facing commercial offer produced by the Merchant Policy Agent.
    
    FIREWALL INVARIANT:
    Exposes only customer-facing terms. Zero COGS, gross margins, predicted contribution,
    LinUCB bandit scores, or exploration uncertainty.
    """
    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(..., description="Unique offer identifier (off_...)")
    strategy_type: str = Field(..., description="Strategy classification (e.g. SINGLE_PRODUCT, BUNDLED_ADDON)")
    items: List[BuyerOfferItem] = Field(default_factory=list, description="Products included in the offer")
    offered_price_paise: int = Field(ge=0, description="Total payable price in integer paise")
    currency: str = Field(default="INR", description="Currency code")
    display_discount_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Customer-visible discount %")
    positioning: Optional[str] = Field(default=None, description="Buyer-visible commercial positioning headline")
    rationale: str = Field(..., description="Customer-visible value proposition")
    expires_at: datetime = Field(..., description="Timestamp when offer expires (freshness TTL)")
    is_executable: bool = Field(default=True, description="Whether this offer can be accepted and checked out")


class BuyerSafeCheckoutResponse(BaseModel):
    """Authoritative response to a checkout execution request.
    
    FINANCIAL SAFETY INVARIANT:
    Razorpay orders are created strictly in Test Mode via deterministic Phase 9.2 Execution Boundary.
    """
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(..., description="Boundary execution record identifier (dexec_...)")
    status: str = Field(..., description="Execution status (SUCCESS, REJECTED, DECISION_STALE, etc.)")
    order_id: Optional[str] = Field(default=None, description="Internal order identifier")
    razorpay_order_id: Optional[str] = Field(default=None, description="Razorpay order identifier (order_...)")
    amount_paise: int = Field(ge=0, description="Authorized payable amount in integer paise")
    currency: str = Field(default="INR", description="Currency code")
    checkout_url: Optional[str] = Field(default=None, description="Payment or checkout URL if available")
    rejection_reasons: List[str] = Field(default_factory=list, description="Reasons if execution was rejected")
    is_duplicate: bool = Field(default=False, description="True if this request was an idempotent replay")


class BuyerSafeOrderStatusView(BaseModel):
    """Buyer-safe transaction and order status view."""
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., description="Internal order identifier")
    razorpay_order_id: Optional[str] = Field(default=None, description="Razorpay order identifier")
    amount_paise: int = Field(ge=0, description="Order amount in paise")
    currency: str = Field(default="INR", description="Currency code")
    status: str = Field(..., description="Authoritative transaction state (e.g. ORDER_CREATED, PAID, FAILED)")
    created_at: Optional[datetime] = Field(default=None, description="Order creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Order status update timestamp")
