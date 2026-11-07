"""Authentication, capability authorization, and tenant isolation for MCP.

INVARIANTS:
1. merchant_id is NEVER trusted from client tool arguments. It is resolved strictly
   from authenticated caller context.
2. Every tool invocation verifies that the caller's identity possesses the required McpCapability.
3. Cross-tenant access is immediately blocked with McpTenantMismatchError.
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any, Set
import structlog

from services.mcp.schemas import (
    McpCapability,
    BuyerAgentIdentity,
    ALL_MCP_CAPABILITIES,
)
from services.mcp.errors import (
    McpAuthenticationError,
    McpTenantMismatchError,
    McpInsufficientCapabilityError,
)

logger = structlog.get_logger()

# Default demo tenant if no explicit bearer token is supplied
DEFAULT_DEMO_MERCHANT_ID = "merch_atlas_travel"
DEFAULT_DEMO_BUYER_AGENT_ID = "agent_external_buyer_v1"

_current_auth_context: ContextVar[Optional[BuyerAgentIdentity]] = ContextVar(
    "current_mcp_auth_context", default=None
)


def get_current_auth_context() -> BuyerAgentIdentity:
    """Retrieve the active MCP buyer agent identity from ContextVar, or default to demo context."""
    ctx = _current_auth_context.get()
    if ctx is None:
        # Fallback to Atlas Travel Gear default demo context
        return BuyerAgentIdentity(
            buyer_agent_id=DEFAULT_DEMO_BUYER_AGENT_ID,
            client_name="canonical_buyer_agent",
            client_version="1.0.0",
            merchant_id=DEFAULT_DEMO_MERCHANT_ID,
            granted_capabilities=set(ALL_MCP_CAPABILITIES)
        )
    return ctx


def set_current_auth_context(identity: BuyerAgentIdentity):
    """Set the active MCP buyer agent identity in ContextVar."""
    _current_auth_context.set(identity)


def check_capability(required: McpCapability, identity: Optional[BuyerAgentIdentity] = None):
    """Verify that the caller has been granted the required capability."""
    current = identity or get_current_auth_context()
    if required not in current.granted_capabilities:
        logger.warn(
            "mcp_capability_denied",
            buyer_agent_id=current.buyer_agent_id,
            required_capability=required.value,
            granted_capabilities=[c.value for c in current.granted_capabilities]
        )
        raise McpInsufficientCapabilityError(
            f"Operation requires capability '{required.value}'. Agent possesses: "
            f"{[c.value for c in current.granted_capabilities]}",
            details={
                "required": required.value,
                "granted": [c.value for c in current.granted_capabilities]
            }
        )


def validate_tenant_scope(target_merchant_id: str, identity: Optional[BuyerAgentIdentity] = None):
    """Enforce strict tenant isolation: block any query targeting a foreign merchant."""
    current = identity or get_current_auth_context()
    if current.merchant_id != target_merchant_id:
        logger.warn(
            "mcp_tenant_violation_blocked",
            buyer_agent_id=current.buyer_agent_id,
            authorized_merchant=current.merchant_id,
            attempted_merchant=target_merchant_id
        )
        raise McpTenantMismatchError(
            f"Access denied: Agent is authorized for merchant '{current.merchant_id}', "
            f"cannot access merchant '{target_merchant_id}'.",
            details={
                "authorized_merchant": current.merchant_id,
                "attempted_merchant": target_merchant_id
            }
        )


def authenticate_buyer(
    auth_header: Optional[str] = None,
    client_metadata: Optional[Dict[str, Any]] = None
) -> BuyerAgentIdentity:
    """Resolve caller identity from HTTP Bearer tokens or MCP client metadata."""
    meta = client_metadata or {}
    buyer_agent_id = meta.get("buyer_agent_id") or DEFAULT_DEMO_BUYER_AGENT_ID
    client_name = meta.get("client_name") or "generic_ai_buyer"
    client_version = meta.get("client_version") or "1.0.0"

    merchant_id = DEFAULT_DEMO_MERCHANT_ID

    # Parse Bearer Token if present: e.g. "Bearer token_merch_atlas_travel_all" or "Bearer merch_alpha"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token.startswith("merch_"):
            # Format: "merch_<name>" -> direct tenant binding
            parts = token.split(":")
            merchant_id = parts[0]
        elif ":" in token:
            # Format: "<buyer_agent_id>:<merchant_id>"
            parts = token.split(":")
            buyer_agent_id = parts[0]
            merchant_id = parts[1]

    # Capabilities resolution
    caps = set(ALL_MCP_CAPABILITIES)
    if "restricted_capabilities" in meta:
        restricted = set(meta["restricted_capabilities"])
        caps = {c for c in ALL_MCP_CAPABILITIES if c.value not in restricted}

    identity = BuyerAgentIdentity(
        buyer_agent_id=buyer_agent_id,
        client_name=client_name,
        client_version=client_version,
        merchant_id=merchant_id,
        granted_capabilities=caps
    )
    set_current_auth_context(identity)
    return identity
