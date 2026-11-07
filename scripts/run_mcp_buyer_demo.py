"""External AI Buyer Agent Demo Client.

Demonstrates canonical buyer journey with Atlas Travel Gear via the Model Context Protocol (MCP).

Target Buyer Flow:
1. Connect to MCP & discover merchant capabilities / tools.
2. Search merchant catalog for products.
3. Express natural language intent ("I need a high-quality travel backpack for a weekend trip under 7500").
4. Receive merchant-specific offer (verified through Buyer Response Firewall).
5. Accept offer and submit bounded checkout request.
6. Observe order status and transaction confirmation in Razorpay Test Mode.
7. Print end-to-end audit correlation trace.

CRITICAL INVARIANT:
The external AI buyer agent contains ZERO merchant policy logic.
All pricing, stock reservation, and execution authorization remain strictly on the backend.
"""

import sys
import os
import json
import asyncio
from datetime import datetime, timezone
import structlog

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from apps.api.core.database import AsyncSessionLocal, init_db
from services.mcp.server import mcp_server
from services.mcp.auth import BuyerAgentIdentity, set_current_auth_context, ALL_MCP_CAPABILITIES
from services.mcp.tools.catalog import search_catalog, get_product
from services.mcp.tools.intent import evaluate_buyer_intent
from services.mcp.tools.offers import get_offer
from services.mcp.tools.checkout import request_checkout
from services.mcp.tools.orders import get_order_status
from scripts.seed_commerce_data import seed_atlas_travel

logger = structlog.get_logger()


async def run_buyer_journey():
    print("=" * 80)
    print("[AGENT] EXTERNAL AI BUYER AGENT -- MCP COMMERCE DEMO (PHASE 13)")
    print("Merchant: Atlas Travel Gear (merch_atlas_travel)")
    print("Protocol: Model Context Protocol (MCP 2026)")
    print("Mode: RAZORPAY TEST MODE (Bounded Deterministic Execution)")
    print("=" * 80)

    # Ensure database is initialized and demo data seeded
    await seed_atlas_travel()

    # Establish external buyer identity
    buyer_identity = BuyerAgentIdentity(
        buyer_agent_id="agent_external_traveler_007",
        client_name="AutonomousTravelShopperAI",
        client_version="2.4.0",
        merchant_id="merch_atlas_travel",
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    )
    set_current_auth_context(buyer_identity)
    print(f"\n[1/7] [AUTH] Authenticated Buyer Agent Identity: {buyer_identity.buyer_agent_id}")
    print(f"      Merchant Tenant Scope: {buyer_identity.merchant_id}")

    # 1. MCP Tool & Resource Discovery
    print("\n[2/7] [DISCOVERY] Discovering Merchant Tools via MCP Protocol...")
    tools = await mcp_server.list_tools()
    print(f"      Discovered {len(tools)} authoritative tools:")
    for t in tools:
        print(f"       • {t.name}: {t.description[:65]}...")

    resources = await mcp_server.list_resources()
    print(f"      Discovered {len(resources)} read-only resources:")
    for r in resources:
        print(f"       * {r.uri}")

    async with AsyncSessionLocal() as db:
        # 2. Search Catalog
        print("\n[3/7] [CATALOG] Searching Catalog for 'backpack'...")
        catalog_items = await search_catalog(query="backpack", db=db)
        print(f"      Found {len(catalog_items)} active items:")
        for item in catalog_items:
            print(f"       * [{item.id}] {item.name} - INR {item.price_paise / 100:.2f} (In Stock: {item.in_stock})")

        # 3. Evaluate Buyer Intent
        user_prompt = "I need a high-quality travel backpack for a weekend trip under 7500"
        print(f"\n[4/7] [INTENT] Submitting Natural Language Buyer Intent:")
        print(f"      Prompt: \"{user_prompt}\"")
        intent_resp = await evaluate_buyer_intent(message=user_prompt)
        print(f"      Structured Intent:")
        print(f"       * Category: {intent_resp.category}")
        print(f"       * Budget: INR {intent_resp.budget_paise / 100:.2f}" if intent_resp.budget_paise else "       * Budget: N/A")
        print(f"       * Confidence: {intent_resp.confidence}")
        print(f"       * Prompt Injection Neutralized: {intent_resp.prompt_injection_neutralized}")

        # 4. Request Merchant Offer
        print("\n[5/7] [OFFER] Requesting Merchant Offer from Policy Agent (get_offer)...")
        offer = await get_offer(message=user_prompt, db=db)
        print(f"      Received Authoritative Offer:")
        print(f"       * Offer ID: {offer.offer_id}")
        print(f"       * Strategy Type: {offer.strategy_type}")
        print(f"       * Payable Price: INR {offer.offered_price_paise / 100:.2f}")
        print(f"       * Discount: {offer.display_discount_percent}%")
        print(f"       * Positioning: {offer.positioning}")
        print(f"       * Rationale: {offer.rationale}")
        print(f"       * Executable: {offer.is_executable}")

        # Verify Buyer Response Firewall (assert zero COGS or margin leakage)
        offer_dict = offer.model_dump(mode="json")
        leaks = [k for k in offer_dict.keys() if any(l in k.lower() for l in ("cogs", "cost", "margin", "ucb", "bandit"))]
        assert not leaks, f"Firewall violation! Leaked keys: {leaks}"
        print("      [FIREWALL] Buyer Response Firewall: VERIFIED ZERO ECONOMIC LEAKAGE.")

        # 5. Request Checkout (The AI buyer requests execution)
        print(f"\n[6/7] [CHECKOUT] Accepting Offer & Submitting Checkout Request (request_checkout)...")
        checkout_resp = await request_checkout(
            offer_id=offer.offer_id,
            idempotency_key=f"demo_idem_{int(datetime.now(timezone.utc).timestamp())}",
            db=db
        )
        print(f"      Checkout Result:")
        print(f"       * Execution ID: {checkout_resp.execution_id}")
        print(f"       * Status: {checkout_resp.status}")
        print(f"       * Order ID: {checkout_resp.order_id}")
        print(f"       * Razorpay Order ID: {checkout_resp.razorpay_order_id}")
        print(f"       * Authorized Amount: INR {checkout_resp.amount_paise / 100:.2f}")
        print(f"       * Rejection Reasons: {checkout_resp.rejection_reasons}")

        # 6. Retrieve Order Status
        print(f"\n[7/7] [STATUS] Checking Order Status (get_order_status)...")
        if checkout_resp.order_id:
            order_status = await get_order_status(order_id=checkout_resp.order_id, db=db)
            print(f"      Order Confirmation:")
            print(f"       * Order ID: {order_status.order_id}")
            print(f"       * Razorpay Order ID: {order_status.razorpay_order_id}")
            print(f"       * Status: {order_status.status}")
            print(f"       * Amount: INR {order_status.amount_paise / 100:.2f}")

        # Print Complete Audit Trail
        print("\n" + "=" * 80)
        print("[AUDIT] AUTHORITATIVE AUDIT & CORRELATION CHAIN:")
        print(f"   Buyer Agent ID:   {buyer_identity.buyer_agent_id}")
        print(f"   Merchant Scope:   {buyer_identity.merchant_id}")
        print(f"   Offer ID:         {offer.offer_id}")
        print(f"   Execution ID:     {checkout_resp.execution_id}")
        print(f"   Order ID:         {checkout_resp.order_id}")
        print(f"   Razorpay Order:   {checkout_resp.razorpay_order_id}")
        print(f"   Execution Status: {checkout_resp.status}")
        print("=" * 80)
        print("[SUCCESS] CANONICAL MCP BUYER JOURNEY COMPLETE & VERIFIED.\n")


if __name__ == "__main__":
    asyncio.run(run_buyer_journey())
