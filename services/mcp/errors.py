"""Typed error taxonomy for the MCP Commerce Adapter.

These exceptions map cleanly to standard JSON-RPC / MCP error responses
with explicit machine-readable error codes.
"""


class McpError(Exception):
    """Base exception for all MCP commerce adapter errors."""
    code: int = -32603  # Internal JSON-RPC error
    error_type: str = "INTERNAL_MCP_ERROR"

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class McpAuthenticationError(McpError):
    """Raised when buyer credentials or token cannot be verified."""
    code: int = -32001
    error_type: str = "AUTHENTICATION_FAILED"


class McpTenantMismatchError(McpError):
    """Raised when an agent attempts to access resources outside its merchant tenant scope."""
    code: int = -32002
    error_type: str = "TENANT_MISMATCH"


class McpInsufficientCapabilityError(McpError):
    """Raised when a caller invokes a tool without the required capability."""
    code: int = -32003
    error_type: str = "INSUFFICIENT_CAPABILITY"


class McpInvalidOfferError(McpError):
    """Raised when an offer ID is invalid, malformed, or references a non-executable offer (e.g. NO_OFFER)."""
    code: int = -32004
    error_type: str = "INVALID_OFFER"


class McpOfferExpiredError(McpError):
    """Raised when an offer has exceeded its freshness TTL."""
    code: int = -32005
    error_type: str = "OFFER_EXPIRED"


class McpSafetyRejectionError(McpError):
    """Raised when an execution request is rejected by deterministic commercial safety."""
    code: int = -32006
    error_type: str = "SAFETY_REJECTED"


class McpProductNotFoundError(McpError):
    """Raised when a requested product cannot be found in the merchant's catalog."""
    code: int = -32007
    error_type: str = "PRODUCT_NOT_FOUND"


class McpOrderNotFoundError(McpError):
    """Raised when an order cannot be found or does not belong to the merchant tenant."""
    code: int = -32008
    error_type: str = "ORDER_NOT_FOUND"
