"""Model Context Protocol (MCP) Server for the Merchant Policy Agent.

Contract: mcp-commerce/v1
Specification: Model Context Protocol 2026

INVARIANTS:
1. The MCP layer is a THIN PROTOCOL ADAPTER.
2. Zero financial authority is granted to the external AI buyer.
3. Every response is filtered through the Buyer Response Firewall.
4. Exposes exactly the 6 authoritative tools and read-only resources.
"""

import sys
import json
import asyncio
from typing import Optional, List, Dict, Any
import structlog
from mcp.server.mcpserver import MCPServer

from services.mcp.schemas import (
    BuyerSafeProductView,
    BuyerSafeIntentResponse,
    BuyerSafeOfferView,
    BuyerSafeCheckoutResponse,
    BuyerSafeOrderStatusView,
)
from services.mcp.tools.catalog import search_catalog as tool_search_catalog, get_product as tool_get_product
from services.mcp.tools.intent import evaluate_buyer_intent as tool_evaluate_buyer_intent
from services.mcp.tools.offers import get_offer as tool_get_offer
from services.mcp.tools.checkout import request_checkout as tool_request_checkout
from services.mcp.tools.orders import get_order_status as tool_get_order_status

logger = structlog.get_logger()


def create_mcp_server() -> MCPServer:
    """Factory creating a fully configured Model Context Protocol server instance."""
    server = MCPServer(
        name="merchant-policy-agent",
        version="1.0.0",
        instructions=(
            "You are connected to the Merchant Policy Agent MCP Interface. "
            "This interface enables external AI buyers to discover merchant products, "
            "evaluate commercial intent, receive tailored merchant offers, request bounded checkout, "
            "and observe order status. All transactions are evaluated deterministically in Test Mode."
        )
    )

    # -------------------------------------------------------------------------
    # 1. TOOL REGISTRATION
    # -------------------------------------------------------------------------

    @server.tool(
        name="search_catalog",
        description=(
            "Discover buyer-visible products in the merchant's catalog. "
            "Supports optional text query, category filter, and max budget constraint."
        )
    )
    async def search_catalog(
        query: Optional[str] = None,
        category: Optional[str] = None,
        max_price_paise: Optional[int] = None,
        currency: str = "INR"
    ) -> List[BuyerSafeProductView]:
        return await tool_search_catalog(
            query=query,
            category=category,
            max_price_paise=max_price_paise,
            currency=currency
        )

    @server.tool(
        name="get_product",
        description="Retrieve detailed buyer-safe information for a single catalog product by its ID."
    )
    async def get_product(product_id: str) -> BuyerSafeProductView:
        return await tool_get_product(product_id=product_id)

    @server.tool(
        name="evaluate_buyer_intent",
        description=(
            "Extract structured commercial intent from natural language buyer prompt. "
            "Neutralizes prompt injections and extracts category, budget, and constraints."
        )
    )
    async def evaluate_buyer_intent(message: str) -> BuyerSafeIntentResponse:
        return await tool_evaluate_buyer_intent(message=message)

    @server.tool(
        name="get_offer",
        description=(
            "Request a merchant-specific commercial offer for a given intent or prompt. "
            "Returns an authoritative offer_id with terms and pricing."
        )
    )
    async def get_offer(
        message: Optional[str] = None,
        buyer_intent: Optional[Dict[str, Any]] = None,
        opportunity_id: Optional[str] = None
    ) -> BuyerSafeOfferView:
        return await tool_get_offer(
            message=message,
            buyer_intent=buyer_intent,
            opportunity_id=opportunity_id
        )

    @server.tool(
        name="request_checkout",
        description=(
            "Accept an offer and request bounded checkout execution. "
            "The external AI buyer requests; deterministic backend code authorizes and creates the order."
        )
    )
    async def request_checkout(
        offer_id: str,
        idempotency_key: Optional[str] = None
    ) -> BuyerSafeCheckoutResponse:
        return await tool_request_checkout(
            offer_id=offer_id,
            idempotency_key=idempotency_key
        )

    @server.tool(
        name="get_order_status",
        description="Retrieve authoritative order status and transaction confirmation."
    )
    async def get_order_status(
        order_id: Optional[str] = None,
        razorpay_order_id: Optional[str] = None
    ) -> BuyerSafeOrderStatusView:
        return await tool_get_order_status(
            order_id=order_id,
            razorpay_order_id=razorpay_order_id
        )

    # -------------------------------------------------------------------------
    # 2. READ-ONLY RESOURCES
    # -------------------------------------------------------------------------

    @server.resource(
        "merchant://capabilities",
        name="merchant_capabilities",
        description="Read-only description of merchant AI commerce capabilities and safety boundaries.",
        mime_type="application/json"
    )
    async def resource_capabilities() -> str:
        capabilities_doc = {
            "protocol": "Model Context Protocol",
            "protocol_version": "2026-07-28",
            "server_version": "1.0.0",
            "merchant_id": "merch_atlas_travel",
            "available_tools": [
                "search_catalog",
                "get_product",
                "evaluate_buyer_intent",
                "get_offer",
                "request_checkout",
                "get_order_status"
            ],
            "financial_authority": "DETERMINISTIC_BACKEND_ONLY",
            "mode": "RAZORPAY_TEST_MODE",
            "data_firewall": "STRICT_BUYER_SAFE_ZERO_COGS"
        }
        return json.dumps(capabilities_doc, indent=2)

    @server.resource(
        "merchant://catalog",
        name="merchant_catalog",
        description="Read-only listing of all currently active products.",
        mime_type="application/json"
    )
    async def resource_catalog() -> str:
        prods = await tool_search_catalog()
        return json.dumps([p.model_dump(mode="json") for p in prods], indent=2)

    return server


# Global default server instance
mcp_server = create_mcp_server()


async def run_stdio():
    """Run the MCP server over standard input/output for desktop agents (e.g. Claude Desktop)."""
    logger.info("mcp_server_starting_stdio")
    await mcp_server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(run_stdio())
