import sqlite3
from datetime import date

conn = sqlite3.connect('test.db')
c = conn.cursor()

print("="*60)
print("DATABASE INTEGRITY & BUSINESS METRICS AUDIT")
print("="*60)

# 1. Product catalog
c.execute("""
    SELECT COUNT(*), SUM(inventory_quantity), SUM(price_paise * inventory_quantity), SUM(cost_paise * inventory_quantity) 
    FROM products WHERE merchant_id = 'merch_atlas_travel'
""")
p_count, total_units, total_retail, total_cost = c.fetchone()
print(f"Products Count        : {p_count} SKUs")
print(f"Total Inventory Units : {total_units} units")
print(f"Total Retail Value    : ₹{total_retail/100:,.2f}")
print(f"Total COGS Value      : ₹{total_cost/100:,.2f}")

# 2. Total orders and paid orders
c.execute("SELECT status, COUNT(*) FROM orders WHERE merchant_id = 'merch_atlas_travel' GROUP BY status")
orders_by_status = dict(c.fetchall())
print(f"Orders Breakdown      : {orders_by_status}")

# 3. 30-day revenue and profit
c.execute("""
    SELECT 
        COUNT(*),
        SUM(total_price_paise),
        SUM(total_cogs_paise)
    FROM orders 
    WHERE merchant_id = 'merch_atlas_travel' AND status = 'PAID'
""")
paid_count, rev_paise, cogs_paise = c.fetchone()
gross_profit_paise = rev_paise - cogs_paise
gross_margin_pct = (gross_profit_paise / rev_paise) * 100
print(f"Paid Orders Total     : {paid_count} orders")
print(f"Total Realized Revenue: ₹{rev_paise/100:,.2f}")
print(f"Total Wholesale COGS  : ₹{cogs_paise/100:,.2f}")
print(f"Total Gross Profit    : ₹{gross_profit_paise/100:,.2f}")
print(f"Effective Gross Margin: {gross_margin_pct:.2f}% (Compliance floor: 25.00%)")

# 4. Channel breakdown
print("\nChannel Contribution Breakdown:")
c.execute("""
    SELECT 
        channel,
        COUNT(*),
        SUM(total_price_paise),
        SUM(total_price_paise - total_cogs_paise)
    FROM orders 
    WHERE merchant_id = 'merch_atlas_travel' AND status = 'PAID'
    GROUP BY channel
    ORDER BY SUM(total_price_paise) DESC
""")
for ch, cnt, ch_rev, ch_prof in c.fetchall():
    ch_margin = (ch_prof / ch_rev) * 100
    print(f"  Channel: {ch:<18} | Orders: {cnt:<3} | Rev: ₹{ch_rev/100:,.2f} | Profit: ₹{ch_prof/100:,.2f} | Margin: {ch_margin:.2f}%")

# 5. Today's orders
today_str = date.today().isoformat()
c.execute("""
    SELECT 
        COUNT(*),
        COALESCE(SUM(total_price_paise), 0),
        COALESCE(SUM(total_price_paise - total_cogs_paise), 0)
    FROM orders 
    WHERE merchant_id = 'merch_atlas_travel' AND status = 'PAID' AND date(created_at) = date(?)
""", (today_str,))
t_orders, t_rev, t_prof = c.fetchone()
t_margin = (t_prof / t_rev * 100) if t_rev > 0 else 0.0
print(f"\nToday ({today_str}) Performance:")
print(f"  Orders Completed    : {t_orders}")
print(f"  Revenue Realized    : ₹{t_rev/100:,.2f}")
print(f"  Gross Profit        : ₹{t_prof/100:,.2f}")
print(f"  Gross Margin        : {t_margin:.2f}%")

