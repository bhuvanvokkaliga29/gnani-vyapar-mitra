"""Tool Declarations and Execution Dispatcher for DoctorAdvisorAgent.

Contains:
1. Formal JSON Schema definitions of all 10 authoritative business tools.
2. Safe dispatcher executing tools against BusinessIntelligenceService.
3. Strict argument validation and error containment.
"""

import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from domain.llm_schemas import LLMToolDefinition, LLMFunctionDeclaration
from services.commerce.business_intelligence import BusinessIntelligenceService

logger = structlog.get_logger()

# =============================================================================
# 1. Declarations of the 10 Business Intelligence Tools
# =============================================================================

DOCTOR_TOOLS: List[LLMToolDefinition] = [
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_daily_sales",
            description="Retrieve exact daily sales, orders, AOV, and top products for today or a specific date.",
            parameters={
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "Optional ISO date (YYYY-MM-DD). If omitted, retrieves today/latest date."
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_sales_summary",
            description="Aggregate sales revenue, volume, and AOV over a historical period (e.g. 7 or 30 days).",
            parameters={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to summarize (default: 7, max: 90)"
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_profit_summary",
            description="Calculate realized gross profit, gross margins, and compliance with the 25% margin floor.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to evaluate (default: 30, max: 90)"
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_top_selling_products",
            description="Rank top-performing products by sales revenue and unit volume.",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of top products to return (default: 5, max: 20)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Historical evaluation window in days (default: 30)"
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_low_stock_products",
            description="Find products nearing stockout with stock levels and urgency indicators.",
            parameters={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "integer",
                        "description": "Units threshold considered low stock (default: 15)"
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_inventory_health",
            description="Audit total inventory value, dead stock, trapped capital, and annual holding costs.",
            parameters={
                "type": "object",
                "properties": {}
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="compare_sales_periods",
            description="Compare revenue and order growth between consecutive time windows (e.g. this week vs last week).",
            parameters={
                "type": "object",
                "properties": {
                    "current_days": {
                        "type": "integer",
                        "description": "Days in current period (default: 7)"
                    },
                    "previous_days": {
                        "type": "integer",
                        "description": "Days in comparison prior period (default: 7)"
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_channel_performance",
            description="Analyze revenue, margins, and marketplace commission leakage across WhatsApp, D2C Web, and Amazon.",
            parameters={
                "type": "object",
                "properties": {}
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="simulate_price_change",
            description="Simulate the margin impact of changing a product price, checking compliance with the 25% floor.",
            parameters={
                "type": "object",
                "required": ["sku_or_id", "new_price_paise"],
                "properties": {
                    "sku_or_id": {
                        "type": "string",
                        "description": "Product SKU (e.g. 'VAST-SHIRT-001') or product ID"
                    },
                    "new_price_paise": {
                        "type": "integer",
                        "description": "Proposed price in paise (1 INR = 100 paise, e.g. 199900 for ₹1,999)"
                    }
                }
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_business_recommendations",
            description="Generate actionable, data-backed recommendations for clearance bundles, reorders, and channel shifts.",
            parameters={
                "type": "object",
                "properties": {}
            }
        )
    ),
    LLMToolDefinition(
        function=LLMFunctionDeclaration(
            name="get_product_stock",
            description="Look up current inventory stock quantity, pricing, and health status for a specific product by SKU or product name.",
            parameters={
                "type": "object",
                "properties": {
                    "sku_or_name": {
                        "type": "string",
                        "description": "Product SKU (e.g. 'VAST-SH-03') or product name (e.g. 'Atlas Travel Shirt')"
                    }
                }
            }
        )
    )
]


# =============================================================================
# 2. Safe Authoritative Tool Dispatcher
# =============================================================================

async def execute_doctor_tool(
    db: AsyncSession,
    merchant_id: str,
    tool_name: str,
    arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate and execute a tool call against the authoritative BI service."""
    logger.info("executing_doctor_tool", tool_name=tool_name, merchant_id=merchant_id, args=arguments)

    try:
        if tool_name == "get_daily_sales":
            target_date = arguments.get("target_date")
            return await BusinessIntelligenceService.get_daily_sales(db, merchant_id, target_date=target_date)

        elif tool_name == "get_sales_summary":
            days = int(arguments.get("days", 7))
            return await BusinessIntelligenceService.get_sales_summary(db, merchant_id, days=days)

        elif tool_name == "get_profit_summary":
            days = int(arguments.get("days", 30))
            return await BusinessIntelligenceService.get_profit_summary(db, merchant_id, days=days)

        elif tool_name == "get_top_selling_products":
            limit = int(arguments.get("limit", 5))
            days = int(arguments.get("days", 30))
            return {"top_products": await BusinessIntelligenceService.get_top_selling_products(db, merchant_id, limit=limit, days=days)}

        elif tool_name == "get_low_stock_products":
            threshold = int(arguments.get("threshold", 15))
            return {"low_stock_products": await BusinessIntelligenceService.get_low_stock_products(db, merchant_id, threshold=threshold)}

        elif tool_name == "get_inventory_health":
            return await BusinessIntelligenceService.get_inventory_health(db, merchant_id)

        elif tool_name == "compare_sales_periods":
            curr_days = int(arguments.get("current_days", 7))
            prev_days = int(arguments.get("previous_days", 7))
            return await BusinessIntelligenceService.compare_sales_periods(db, merchant_id, curr_days, prev_days)

        elif tool_name == "get_channel_performance":
            return await BusinessIntelligenceService.get_channel_performance(db, merchant_id)

        elif tool_name == "simulate_price_change":
            sku_or_id = str(arguments.get("sku_or_id", "")).strip()
            price_paise = int(arguments.get("new_price_paise", 0))
            return await BusinessIntelligenceService.simulate_price_change(db, merchant_id, sku_or_id, price_paise)

        elif tool_name == "get_business_recommendations":
            return await BusinessIntelligenceService.get_business_recommendations(db, merchant_id)

        elif tool_name == "get_product_stock":
            sku_or_name = str(arguments.get("sku_or_name", "")).strip()
            from domain.models import Product
            from sqlalchemy import select, or_
            query = select(Product).where(Product.merchant_id == merchant_id)
            if sku_or_name:
                query = query.where(
                    or_(
                        Product.sku.ilike(f"%{sku_or_name}%"),
                        Product.name.ilike(f"%{sku_or_name}%")
                    )
                )
            prod = (await db.execute(query)).scalars().first()
            if not prod and sku_or_name:
                first_token = sku_or_name.split()[0]
                query = select(Product).where(
                    Product.merchant_id == merchant_id,
                    or_(
                        Product.sku.ilike(f"%{first_token}%"),
                        Product.name.ilike(f"%{first_token}%")
                    )
                )
                prod = (await db.execute(query)).scalars().first()
            if prod:
                return {
                    "product_name": prod.name,
                    "sku": prod.sku,
                    "available_stock": prod.inventory_quantity,
                    "price_formatted": f"₹{prod.price_paise / 100:,.2f}",
                    "cost_formatted": f"₹{prod.cost_paise / 100:,.2f}",
                    "stock_status": "Safe" if prod.inventory_quantity > 15 else "Low Stock"
                }
            return {"error": f"Product '{sku_or_name}' not found in store catalog."}

        else:
            logger.warning("unknown_tool_requested", tool_name=tool_name)
            return {"error": f"Tool '{tool_name}' is not recognized."}

    except Exception as exc:
        logger.error("tool_execution_exception", tool_name=tool_name, error=str(exc))
        return {"error": f"Failed to execute tool '{tool_name}': {str(exc)}"}

