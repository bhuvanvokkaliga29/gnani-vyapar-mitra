"""Model Context Protocol (MCP) Interface for the Merchant Policy Agent."""

from services.mcp.schemas import (
    McpCapability,
    ALL_MCP_CAPABILITIES,
    READ_ONLY_CAPABILITIES,
    BuyerAgentIdentity,
    BuyerSafeProductView,
    BuyerSafeIntentResponse,
    BuyerSafeOfferView,
    BuyerOfferItem,
    BuyerSafeCheckoutResponse,
    BuyerSafeOrderStatusView,
)
from services.mcp.errors import (
    McpError,
    McpTenantMismatchError,
    McpInsufficientCapabilityError,
    McpAuthenticationError,
    McpInvalidOfferError,
    McpOfferExpiredError,
    McpSafetyRejectionError,
    McpProductNotFoundError,
    McpOrderNotFoundError,
)
from services.mcp.server import mcp_server, create_mcp_server
from services.mcp.tools import (
    search_catalog,
    get_product,
    evaluate_buyer_intent,
    get_offer,
    request_checkout,
    get_order_status,
)

__all__ = [
    "mcp_server",
    "create_mcp_server",
    "McpCapability",
    "BuyerAgentIdentity",
    "BuyerSafeProductView",
    "BuyerSafeIntentResponse",
    "BuyerSafeOfferView",
    "BuyerOfferItem",
    "BuyerSafeCheckoutResponse",
    "BuyerSafeOrderStatusView",
    "McpError",
    "McpTenantMismatchError",
    "McpInsufficientCapabilityError",
    "McpAuthenticationError",
    "McpInvalidOfferError",
    "McpOfferExpiredError",
    "McpSafetyRejectionError",
    "McpProductNotFoundError",
    "McpOrderNotFoundError",
    "search_catalog",
    "get_product",
    "evaluate_buyer_intent",
    "get_offer",
    "request_checkout",
    "get_order_status",
]
