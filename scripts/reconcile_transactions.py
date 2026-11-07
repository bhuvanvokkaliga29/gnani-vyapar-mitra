import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('test.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
m = 'merch_atlas_travel'

cur.execute('''
    SELECT 
        o.id as outcome_id,
        o.razorpay_payment_id,
        o.decision_id,
        d.selected_policy_id,
        o.transaction_state,
        o.outcome_status,
        o.realized_revenue_paise,
        o.realized_cogs_paise,
        o.reward_contribution_paise
    FROM outcome_feedbacks o
    JOIN canonical_decisions d ON o.decision_id = d.id
    WHERE o.merchant_id = ?
    ORDER BY o.created_at
''', (m,))

rows = [dict(r) for r in cur.fetchall()]
print(f"Total outcomes: {len(rows)}")
print("| Outcome ID | Payment ID | Policy | State | Revenue | COGS | Contribution | Paid? | In Test-Mode? |")
tot_contrib = 0
paid_count = 0
for r in rows:
    is_paid = (r['transaction_state'] == 'PAID' or r['outcome_status'] == 'PAYMENT_SUCCESS')
    if is_paid:
        paid_count += 1
        tot_contrib += r['reward_contribution_paise']
    paid_str = 'YES' if is_paid else 'NO'
    tm_str = 'YES' if is_paid else 'NO'
    print(f"| {r['outcome_id']} | {r['razorpay_payment_id']} | {r['selected_policy_id']} | {r['transaction_state']} | {r['realized_revenue_paise']} | {r['realized_cogs_paise']} | {r['reward_contribution_paise']} | {paid_str} | {tm_str} |")

print(f"Aggregates: Paid Count = {paid_count}, Total Contribution = {tot_contrib} paise (Rs. {tot_contrib/100:.2f})")
conn.close()
