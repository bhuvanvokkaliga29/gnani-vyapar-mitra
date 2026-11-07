import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('test.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
m = 'merch_atlas_travel'

cur.execute('''
    SELECT 
        d.id as decision_id,
        d.opportunity_id,
        d.decision_mode,
        d.selected_strategy_type,
        d.selected_policy_id,
        d.proposed_price_paise,
        d.predicted_contribution_paise,
        de.boundary_status
    FROM canonical_decisions d
    LEFT JOIN decision_executions de ON d.id = de.decision_id
    WHERE d.merchant_id = ?
    ORDER BY d.created_at
''', (m,))

rows = [dict(r) for r in cur.fetchall()]
print(f"Total decisions: {len(rows)}")
print("| Decision ID | Opp ID | Mode | Strategy | Policy | Predicted (paise) | Predicted (Rs) | Status | Included in Sum? |")
total_predicted = 0
for r in rows:
    pred = r['predicted_contribution_paise']
    total_predicted += pred
    status = r['boundary_status'] or 'PENDING_GATE'
    print(f"| {r['decision_id']} | {r['opportunity_id']} | {r['decision_mode']} | {r['selected_strategy_type']} | {r['selected_policy_id']} | {pred} | {pred/100:.2f} | {status} | YES (all evaluated decisions) |")

print(f"\nTotal Predicted Contribution: {total_predicted} paise = Rs. {total_predicted/100:.2f}")

# Breakdown by boundary status
cur.execute('''
    SELECT 
        COALESCE(de.boundary_status, 'PENDING_EXECUTION_GATE') as status,
        count(d.id) as cnt,
        sum(d.predicted_contribution_paise) as pred_sum
    FROM canonical_decisions d
    LEFT JOIN decision_executions de ON d.id = de.decision_id
    WHERE d.merchant_id = ?
    GROUP BY status
''', (m,))
for r in cur.fetchall():
    print(f"By status {r['status']}: count={r['cnt']}, sum_paise={r['pred_sum']} (Rs. {r['pred_sum']/100:.2f})")

# Breakdown by strategy / NO_OFFER
cur.execute('''
    SELECT 
        d.selected_strategy_type,
        count(d.id) as cnt,
        sum(d.predicted_contribution_paise) as pred_sum
    FROM canonical_decisions d
    WHERE d.merchant_id = ?
    GROUP BY d.selected_strategy_type
''', (m,))
for r in cur.fetchall():
    print(f"By strategy {r['selected_strategy_type']}: count={r['cnt']}, sum_paise={r['pred_sum']} (Rs. {r['pred_sum']/100:.2f})")

conn.close()
