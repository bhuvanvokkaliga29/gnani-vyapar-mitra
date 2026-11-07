"""Interactive Gemini AI Buyer Agent for MCP Commerce Interface.

Allows natural language interaction with the Merchant Policy Agent via MCP.
Translates prompts into Model Context Protocol tool calls:
- search_catalog
- evaluate_buyer_intent
- get_offer
- request_checkout
- get_order_status
"""

import sys
import os
import asyncio
import uuid
import structlog

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from services.mcp.auth import BuyerAgentIdentity, set_current_auth_context, ALL_MCP_CAPABILITIES
from services.mcp.tools.catalog import search_catalog, get_product
from services.mcp.tools.intent import evaluate_buyer_intent
from services.mcp.tools.offers import get_offer
from services.mcp.tools.checkout import request_checkout
from services.mcp.tools.orders import get_order_status
from scripts.seed_commerce_data import seed_atlas_travel

logger = structlog.get_logger()


class GeminiBuyerSession:
    def __init__(self, merchant_id: str = "merch_atlas_travel"):
        self.merchant_id = merchant_id
        self.buyer_id = f"gemini_buyer_{uuid.uuid4().hex[:6]}"
        self.last_offer = None
        self.last_order = None

    async def initialize(self):
        await seed_atlas_travel()
        identity = BuyerAgentIdentity(
            buyer_agent_id=self.buyer_id,
            client_name="GeminiCommerceBuyer",
            client_version="1.0.0",
            merchant_id=self.merchant_id,
            granted_capabilities=set(ALL_MCP_CAPABILITIES)
        )
        set_current_auth_context(identity)

    async def process_user_prompt(self, prompt: str) -> str:
        prompt_lower = prompt.lower().strip()

        # 1. Checkout request
        if any(w in prompt_lower for w in ["checkout", "buy it", "buy now", "purchase", "proceed", "accept"]):
            if not self.last_offer:
                return "[GEMINI BUYER] You haven't requested an offer yet! Try asking: 'Get me an offer for a travel backpack under 7500'"
            
            offer_id = self.last_offer.offer_id
            print(f"--> [GEMINI MCP TOOL] request_checkout(offer_id='{offer_id}')")
            res = await request_checkout(offer_id=offer_id, idempotency_key=str(uuid.uuid4()))
            if res.status == "EXECUTION_COMPLETED":
                self.last_order = res
                return (
                    f"[GEMINI BUYER] Checkout Successful!\n"
                    f"  * Order ID: {res.order_id}\n"
                    f"  * Razorpay Order ID: {res.razorpay_order_id}\n"
                    f"  * Authorized Amount: INR {res.amount_paise / 100:.2f}\n"
                    f"  * Status: {res.status}\n"
                    f"  * Mode: RAZORPAY TEST MODE (Inventory locked atomically)\n"
                    f"  * Checkout URL: {res.checkout_url}"
                )
            else:
                return f"[GEMINI BUYER] Checkout rejected by merchant: {res.rejection_reasons}"

        # 2. Order status request
        if any(w in prompt_lower for w in ["order status", "status of order", "my order", "tracking"]):
            if not self.last_order:
                return "[GEMINI BUYER] No active order in this session. Complete a checkout first!"
            
            order_id = self.last_order.order_id
            print(f"--> [GEMINI MCP TOOL] get_order_status(order_id='{order_id}')")
            res = await get_order_status(order_id=order_id)
            return (
                f"[GEMINI BUYER] Authoritative Order Confirmation:\n"
                f"  * Order ID: {res.order_id}\n"
                f"  * Razorpay ID: {res.razorpay_order_id}\n"
                f"  * Status: {res.status}\n"
                f"  * Amount: INR {res.amount_paise / 100:.2f}\n"
                f"  * Created At: {res.created_at}"
            )

        # 3. Product catalog search request
        if any(w in prompt_lower for w in ["products", "catalog", "what do you have", "show items", "list items", "search", "inventory"]):
            category = None
            if "backpack" in prompt_lower:
                category = "travel_backpack"
            elif "sleeve" in prompt_lower or "laptop" in prompt_lower:
                category = "accessories"
            
            print(f"--> [GEMINI MCP TOOL] search_catalog(category={category})")
            prods = await search_catalog(category=category)
            if not prods:
                return "[GEMINI BUYER] No products matched your query in the catalog."
            
            lines = [f"[GEMINI BUYER] Found {len(prods)} active products from Atlas Travel Gear:"]
            for p in prods:
                stock_label = "[IN STOCK]" if p.in_stock else "[OUT OF STOCK]"
                price_inr = p.price_paise / 100.0
                lines.append(f"  * [{p.id}] {p.name} - INR {price_inr:.2f} {stock_label}")
                if p.description:
                    lines.append(f"    Description: {p.description}")
            return "\n".join(lines)

        # 4. Intent & Offer evaluation (default for purchasing desires)
        print(f"--> [GEMINI MCP TOOL] evaluate_buyer_intent(message='{prompt}')")
        intent = await evaluate_buyer_intent(message=prompt)
        
        print(f"--> [GEMINI MCP TOOL] get_offer(message='{prompt}')")
        offer = await get_offer(message=prompt)
        
        if not offer.is_executable or offer.strategy_type == "NO_OFFER":
            budget_str = f"INR {intent.budget_paise / 100:.2f}" if intent.budget_paise else "Not specified"
            return (
                f"[GEMINI BUYER] Merchant evaluated your intent ({intent.category} - Budget: {budget_str}), "
                f"but returned NO_OFFER because commercial safety boundaries (margin floors or stock limits) were reached."
            )
        
        self.last_offer = offer
        items_str = ", ".join([f"{item.product_id} (x{item.quantity}) at INR {item.unit_price_paise / 100:.2f}" for item in offer.items])
        total_inr = offer.offered_price_paise / 100.0
        return (
            f"[GEMINI BUYER] Received Tailored Offer from Atlas Travel Gear:\n"
            f"  * Offer ID: {offer.offer_id}\n"
            f"  * Strategy: {offer.strategy_type}\n"
            f"  * Items: {items_str}\n"
            f"  * Total Price: INR {total_inr:.2f} (Discount: {offer.display_discount_percent:.1f}%)\n"
            f"  * Rationale: {offer.rationale}\n"
            f"  * Positioning: {offer.positioning}\n\n"
            f"👉 Type 'checkout' or 'buy now' to authorize this purchase in Razorpay Test Mode!"
        )


async def main():
    print("=" * 80)
    print("🤖 GEMINI AI BUYER AGENT -- INTERACTIVE MCP COMMERCE CONSOLE")
    print("Merchant: Atlas Travel Gear (merch_atlas_travel)")
    print("Protocol: Model Context Protocol (MCP 2026)")
    print("=" * 80)
    
    session = GeminiBuyerSession()
    await session.initialize()
    
    print("\n[READY] Gemini Buyer Agent is connected to the merchant MCP server.")
    print("Examples to try:")
    print("  1. 'What products do you have?'")
    print("  2. 'I want a durable travel backpack under 8000 for weekend trips'")
    print("  3. 'checkout'")
    print("  4. 'order status'")
    print("  (Type 'exit' to quit)\n")

    while True:
        try:
            user_input = input("Gemini Buyer > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting Gemini Buyer Agent console. Goodbye!")
                break
            
            response = await session.process_user_prompt(user_input)
            print(f"\n{response}\n")
            print("-" * 60)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
