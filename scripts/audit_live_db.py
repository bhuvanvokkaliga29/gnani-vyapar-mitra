import sqlite3
import json

db_path = "test.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

m = "merch_atlas_travel"

print(f"=== SECTION 1: LIVE DATA AUDIT FOR {m} ===")

# 0. Tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables in db: {tables}")

# 1. Opportunities / Canonical Decisions
# Let's see how opportunities are stored (or if canonical_decisions has opportunity_id)
if 'opportunities' in tables:
    cur.execute("SELECT count(*) FROM opportunities WHERE merchant_id = ?", (m,))
    total_opps = cur.fetchone()[0]
else:
    # Distinct opportunity_id in canonical_decisions
    cur.execute("SELECT count(DISTINCT opportunity_id) FROM canonical_decisions WHERE merchant_id = ?", (m,))
    total_opps = cur.fetchone()[0]
print(f"Total opportunities: {total_opps}")

# Helper to inspect table columns
def get_cols(tbl):
    cur.execute(f"PRAGMA table_info({tbl})")
    return [r[1] for r in cur.fetchall()]

for tbl in ['canonical_decisions', 'decision_executions', 'outcome_feedbacks', 'learning_evidence', 'policy_memory', 'applied_model_observations', 'policy_safety_records', 'merchant_exploration_states', 'merchant_active_policies', 'payments']:
    if tbl in tables:
        print(f"Schema {tbl}: {get_cols(tbl)}")

# 1. Opportunities & Canonical Decisions
cur.execute("SELECT count(DISTINCT opportunity_id) FROM canonical_decisions WHERE merchant_id = ?", (m,))
total_opps = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM canonical_decisions WHERE merchant_id = ?", (m,))
total_decisions = cur.fetchone()[0]
print(f"Total opportunities: {total_opps}")
print(f"Total canonical decisions: {total_decisions}")

# 2. Decision Executions
cur.execute("SELECT boundary_status, count(*) FROM decision_executions WHERE merchant_id = ? GROUP BY boundary_status", (m,))
print(f"decision_executions by boundary_status: {[dict(r) for r in cur.fetchall()]}")

cur.execute("SELECT count(*) FROM decision_executions WHERE merchant_id = ?", (m,))
total_executions = cur.fetchone()[0]
print(f"Total decision executions: {total_executions}")

# Policy Safety Records
cur.execute("SELECT status, count(*) FROM policy_safety_records WHERE merchant_id = ? GROUP BY status", (m,))
print(f"policy_safety_records by status: {[dict(r) for r in cur.fetchall()]}")

import sys
sys.stdout.reconfigure(encoding='utf-8')

# 3. Outcome Feedbacks & Transactions
cur.execute("SELECT transaction_state, count(*) FROM outcome_feedbacks WHERE merchant_id = ? GROUP BY transaction_state", (m,))
print(f"outcome_feedbacks by transaction_state: {[dict(r) for r in cur.fetchall()]}")

cur.execute("SELECT outcome_status, count(*) FROM outcome_feedbacks WHERE merchant_id = ? GROUP BY outcome_status", (m,))
print(f"outcome_feedbacks by outcome_status: {[dict(r) for r in cur.fetchall()]}")

# Let's inspect a few rows of outcome_feedbacks
cur.execute("SELECT id, transaction_state, outcome_status, reward_contribution_paise, realized_revenue_paise, realized_cogs_paise FROM outcome_feedbacks WHERE merchant_id = ? LIMIT 10", (m,))
for r in cur.fetchall():
    print(f"  outcome_feedback row: {dict(r)}")

# 4. Learning Evidence
cur.execute("SELECT count(*) FROM learning_evidence WHERE merchant_id = ?", (m,))
total_evidence = cur.fetchone()[0]
cur.execute("SELECT evidence_status, learning_eligible, count(*) FROM learning_evidence WHERE merchant_id = ? GROUP BY evidence_status, learning_eligible", (m,))
print(f"learning_evidence status & eligibility: {[dict(r) for r in cur.fetchall()]}")
print(f"Total learning evidence: {total_evidence}")

# 5. Policy Memory
cur.execute("SELECT count(*) FROM policy_memory WHERE merchant_id = ?", (m,))
total_memories = cur.fetchone()[0]
print(f"Total policy memory: {total_memories}")
cur.execute("SELECT outcome_type, is_admissible, count(*) FROM policy_memory WHERE merchant_id = ? GROUP BY outcome_type, is_admissible", (m,))
print(f"policy_memory by outcome & admissibility: {[dict(r) for r in cur.fetchall()]}")

# 6. Applied Model Observations
if 'applied_model_observations' in tables:
    cur.execute("SELECT count(*) FROM applied_model_observations WHERE merchant_id = ?", (m,))
    total_applied = cur.fetchone()[0]
    print(f"Total applied model observations: {total_applied}")

# 7. Model Observation Count
if 'policy_learning_model_states' in tables:
    cur.execute(f"PRAGMA table_info(policy_learning_model_states)")
    print(f"policy_learning_model_states cols: {[r[1] for r in cur.fetchall()]}")
    cur.execute("SELECT * FROM policy_learning_model_states WHERE merchant_id = ?", (m,))
    for r in cur.fetchall():
        print(f"  policy_learning_model_states: {dict(r)}")

cur.execute("SELECT * FROM merchant_exploration_states WHERE merchant_id = ?", (m,))
exp_state = cur.fetchone()
if exp_state:
    print(f"merchant_exploration_states: {dict(exp_state)}")

# 8. Active Policy
cur.execute("SELECT * FROM merchant_active_policies WHERE merchant_id = ?", (m,))
act_pol = cur.fetchone()
print(f"merchant_active_policies: {dict(act_pol) if act_pol else None}")

# 9. Evidence by Policy
cur.execute("SELECT policy_id, count(*), sum(observed_contribution_paise) FROM learning_evidence WHERE merchant_id = ? GROUP BY policy_id", (m,))
print(f"learning_evidence by policy_id: {[dict(r) for r in cur.fetchall()]}")

# 10. Realized Margin / Observed Contribution
cur.execute("SELECT sum(reward_contribution_paise) FROM outcome_feedbacks WHERE merchant_id = ?", (m,))
sum_reward_contribution = cur.fetchone()[0]
print(f"Total reward_contribution_paise in outcome_feedbacks: {sum_reward_contribution} (₹{sum_reward_contribution/100:.2f})")

# By Policy in outcome_feedbacks
cur.execute("""
    SELECT d.selected_policy_id, sum(o.reward_contribution_paise), sum(o.realized_revenue_paise), count(*)
    FROM outcome_feedbacks o
    JOIN canonical_decisions d ON o.decision_id = d.id
    WHERE o.merchant_id = ?
    GROUP BY d.selected_policy_id
""", (m,))
print(f"Outcome feedbacks by policy_id: {[dict(r) for r in cur.fetchall()]}")

# By Outcome Status / Transaction State
cur.execute("""
    SELECT transaction_state, sum(reward_contribution_paise), sum(realized_revenue_paise), count(*)
    FROM outcome_feedbacks
    WHERE merchant_id = ?
    GROUP BY transaction_state
""", (m,))
print(f"Outcome feedbacks by transaction_state: {[dict(r) for r in cur.fetchall()]}")

# 11. Expected Margin / Predicted Contribution
cur.execute("SELECT sum(predicted_contribution_paise) FROM canonical_decisions WHERE merchant_id = ?", (m,))
sum_predicted_contribution = cur.fetchone()[0]
print(f"Total predicted_contribution_paise (paise): {sum_predicted_contribution} (₹{sum_predicted_contribution/100:.2f})")

# 12. Exploration vs Exploitation vs NO_OFFER
cur.execute("SELECT decision_mode, count(*) FROM canonical_decisions WHERE merchant_id = ? GROUP BY decision_mode", (m,))
print(f"canonical_decisions by decision_mode: {[dict(r) for r in cur.fetchall()]}")

cur.execute("SELECT selected_strategy_type, count(*) FROM canonical_decisions WHERE merchant_id = ? GROUP BY selected_strategy_type", (m,))
print(f"canonical_decisions by selected_strategy_type: {[dict(r) for r in cur.fetchall()]}")

cur.execute("SELECT count(*) FROM canonical_decisions WHERE merchant_id = ? AND (selected_strategy_type = 'NO_OFFER' OR selected_policy_id = 'cand_base_no_offer')", (m,))
print(f"NO_OFFER count: {cur.fetchone()[0]}")

conn.close()


conn.close()
