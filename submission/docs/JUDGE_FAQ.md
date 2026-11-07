# Final Judge & Evaluator FAQ

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> **System**: Merchant Policy Agent  
> **Release Candidate**: 1.0.0-rc (Frozen)

---

### 1. Why is Razorpay essential to this system?
Razorpay provides the **authoritative financial truth layer** for the entire closed-loop learning cycle. In agentic commerce, an AI decision is merely an unverified hypothesis until funds are captured. Razorpay creates the orders, captures payments, and issues webhooks that trigger outcome feedback. Without Razorpay, the agent would be operating on hallucinated or unverified buyer acceptance rather than real economic transactions.

---

### 2. How does the agent learn?
The agent uses an online **Contextual Multi-Armed Bandit (LinUCB with disjoint ridge regression)**. When an AI buyer opportunity arrives, a 19-dimensional context-policy feature vector $x$ is constructed from buyer constraints, category, price tiers, and commercial policy strategy. When a transaction completes, the reward $r$ (exact gross contribution in paise) updates the policy's covariance matrix $A \leftarrow A + x x^T$ and bias vector $b \leftarrow b + r x$. Future decisions balance exploitation ($\theta^T x$) with exploration uncertainty ($\alpha \sqrt{x^T A^{-1} x}$).

---

### 3. What prevents the LLM from giving discounts freely?
The LLM has **zero execution authority**. The LLM (or policy generator) acts purely as an advisory proposer. Every candidate proposal must pass through deterministic Python validation code (`PolicySafetyValidator`) that checks the merchant's configured discount ceiling (e.g. 20%) and margin floor (e.g. 25%). Any proposal exceeding the discount ceiling is filtered out before selection.

---

### 4. How is merchant margin protected?
Margin protection is enforced at two distinct stages:
1. **Selection Stage**: Candidates with negative gross profit or margins below the merchant's configured margin floor are declared inadmissible.
2. **Fresh Execution Stage**: Before submitting to Razorpay, the execution boundary re-queries the authoritative product catalog to verify real-time COGS and active pricing, guaranteeing that price fluctuations or stale cache states cannot cause a below-margin sale.

---

### 5. How is learning separated from promotion?
**Learning $\neq$ Promotion**. 
- **Learning**: The bandit model continuously updates its continuous mathematical weights $\theta = A^{-1}b$ on every payment outcome to improve future exploration choices.
- **Promotion**: Promoting an experimental policy to become the merchant's active baseline requires meeting immutable governance gates (`PolicyLifecycleService`): minimum sample size (e.g. $\ge 10$ observations), strictly positive observed contribution, and zero margin floor violations. If criteria fail, promotion is safely rejected with audit logs.

---

### 6. What happens when payment fails or checkout is abandoned?
When a buyer abandons checkout or payment fails (`status: "failed"`):
1. The execution boundary releases any reserved inventory back to available stock.
2. An `OutcomeFeedbackRecord` is created with `transaction_state: "FAILED"` and `reward_contribution_paise: 0`.
3. The LinUCB model incorporates this ₹0 reward for the chosen strategy, learning that this policy failed to convert in this specific buyer context.

---

### 7. What happens when inventory changes after a decision is evaluated?
Between decision evaluation and execution, stock may be purchased by another customer. The execution boundary executes **Fresh Safety Validation** against the live database and attempts atomic inventory reservation (`SELECT ... FOR UPDATE` semantics). If inventory has depleted to zero, execution is immediately aborted with status `SAFETY_REJECTED / INSUFFICIENT_INVENTORY`, preventing overselling.

---

### 8. How do you prevent duplicate learning from replayed webhooks?
Every outcome feedback request requires an `idempotency_key` and is checked against the database. If a webhook is delivered twice, `OutcomeFeedbackService` detects the existing record, logs an `outcome_feedback_idempotent_replay` event, and returns the existing outcome without applying duplicate covariance updates to the LinUCB model.

---

### 9. How do you prevent multi-tenant data leakage?
All database queries, runtime executions, bandit states, catalog entities, and dashboard APIs require explicit `merchant_id` tenant keys:
- Product catalogs and affinity relationships reject cross-tenant references.
- Bandit models and covariance matrices are isolated per merchant tenant.
- Attempting to access or execute an order belonging to Merchant A using Merchant B credentials immediately triggers an authorization error / `MerchantNotFoundError`.

---

### 10. How do you know the dashboard is truthful and not showing fake numbers?
The Merchant AI Control Center is strictly a **read plane** connected to persistent SQLite/PostgreSQL database tables. Every KPI on the dashboard (opportunities, decisions, paid transactions, observed contribution, expected contribution) is verified by automated reconciliation tests (`test_dashboard_semantic_reconciliation.py`) that compare the Service DTO output against direct, raw SQL aggregate queries (`SELECT COUNT(*)`, `SELECT SUM()`).

---

### 11. Is this production data?
**No**. The merchant profile (Atlas Travel Gear), products, and buyer requests are synthetic demo datasets designed to demonstrate realistic commercial scenarios (business travel bundling, budget-sensitive refusal, stock exhaustion).

---

### 12. Is this production payment processing?
**No**. The system operates strictly in **Razorpay Test Mode** (`rzp_test_...`). No live credit cards, UPI accounts, or real funds are debited or settled.

---

### 13. What are the current system limitations?
- **Test Mode Only**: No live banking rails or asynchronous chargebacks.
- **Linear Bandit**: LinUCB assumes a linear relationship between features and contribution; non-linear deep RL is out of scope.
- **Gross Contribution Scope**: The economic reward formula models gross contribution ($Revenue - COGS$); it does not currently deduct shipping, taxes (GST), or gateway MDR fees.
- **Controlled Buyer Traffic**: Buyer behavior is generated by simulation archetypes rather than live consumer traffic.
