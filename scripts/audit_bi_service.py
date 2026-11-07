import sys, os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import json
from apps.api.core.database import AsyncSessionLocal
from services.commerce.business_intelligence import BusinessIntelligenceService
from services.agent.doctor_tools import execute_doctor_tool

async def audit():
    async with AsyncSessionLocal() as db:
        m_id = "merch_atlas_travel"
        sales = await BusinessIntelligenceService.get_daily_sales(db, m_id)
        profit = await BusinessIntelligenceService.get_profit_summary(db, m_id, days=30)
        channels = await BusinessIntelligenceService.get_channel_performance(db, m_id)
        inv = await BusinessIntelligenceService.get_inventory_health(db, m_id)
        stock = await execute_doctor_tool(db, m_id, "get_product_stock", {"sku_or_name": "VAST-SH-03"})

        print("=== 1. DAILY SALES METRICS ===")
        print(f"  Date               : {sales.get('date')}")
        print(f"  Paid Orders        : {sales.get('paid_orders')}")
        print(f"  Total Revenue      : {sales.get('revenue_formatted')}")
        print(f"  Gross Profit       : {sales.get('gross_profit_formatted')}")
        print(f"  Gross Margin       : {sales.get('gross_margin_percent')}%")
        print(f"  AOV                : {sales.get('aov_formatted')}")
        print(f"  Top Selling Item   : {(sales.get('top_products') or [{}])[0].get('name')}")

        print("\n=== 2. 30-DAY PROFIT SUMMARY ===")
        print(f"  Total Revenue      : {profit.get('total_revenue_formatted')}")
        print(f"  Total COGS         : ₹{profit.get('total_cogs_paise', 0)/100:,.2f}")
        print(f"  Gross Profit       : {profit.get('gross_profit_formatted')}")
        print(f"  Gross Margin       : {profit.get('gross_margin_percent')}%")
        print(f"  Floor Compliance   : {'✅ COMPLIANT' if profit.get('is_above_policy_floor') else '❌ VIOLATION'} (Floor: {profit.get('policy_margin_floor_percent')}%)")

        print("\n=== 3. CHANNEL ECONOMICS ===")
        for ch in channels.get("channels", []):
            code = ch.get("channel_code")
            name = ch.get("name")
            contrib = ch.get("net_contribution_typical_pct")
            rto = ch.get("rto_rate") * 100
            status = ch.get("status")
            print(f"  {code:<12} ({name:<35}) : Net Margin={contrib}% | RTO={rto:.0f}% | Status={status}")

        print("\n=== 4. INVENTORY HEALTH ===")
        print(f"  Total Catalog Lines: {inv.get('total_products_count')} SKUs")
        print(f"  Total Stock Value  : {inv.get('total_inventory_value_formatted')}")
        print(f"  Trapped Capital    : {inv.get('total_trapped_capital_formatted')} ({inv.get('dead_stock_count')} slow-moving lines)")
        print(f"  Holding Cost/yr    : {inv.get('annual_holding_cost_formatted')}")
        print(f"  Low Stock SKUs     : {inv.get('low_stock_count')} lines needing reorder")

        print("\n=== 5. FOCUSED PRODUCT STOCK (VAST-SH-03) ===")
        print(f"  SKU                : {stock.get('sku')}")
        print(f"  Product Name       : {stock.get('product_name')}")
        print(f"  Available Stock    : {stock.get('available_stock')} units")
        print(f"  Retail Price       : {stock.get('price_formatted')}")
        print(f"  Wholesale Cost     : {stock.get('cost_formatted')}")
        print(f"  Stock Status       : {stock.get('stock_status')}")

if __name__ == "__main__":
    asyncio.run(audit())
