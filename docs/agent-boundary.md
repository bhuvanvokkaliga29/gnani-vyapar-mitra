# Agent Boundary: The Inviolable Partition

This document defines the strict, non-negotiable architectural partition between probabilistic LLM reasoning and deterministic financial code.

---

## 1. The Core Architectural Axiom

# THE LLM CAN PROPOSE. IT CANNOT SPEND.

No large language model possesses direct network access, credentials, or function-calling authority to initiate orders, move money, alter accounts, or invoke Razorpay APIs.

Any design that allows:
```text
LLM ──[Direct Tool Call]──> Razorpay Orders API   ❌ FORBIDDEN
```
is rejected as an unacceptable financial risk.

Instead, the system enforces a unidirectional, gated execution pipeline:
```text
                       ┌─────────────────────────┐
                       │  Probabilistic LLM      │
                       │  Reasoning Engine       │
                       └────────────┬────────────┘
                                    │
                         Generates candidate JSON
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Pydantic v2 Schema     │
                       │  Structural Validation  │
                       └────────────┬────────────┘
                                    │
                         Strict typed proposal
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Deterministic Policy   │
                       │  & Economic Engine      │
                       │  (Margin, Budget, COGS) │
                       └────────────┬────────────┘
                                    │
                          Gated Approval / Reject
                                    │
                        [APPROVED]  │  [REJECTED] ──> Log Audit & Fallback
                                    ▼
                       ┌─────────────────────────┐
                       │  Razorpay Adapter       │
                       │  (Pure Deterministic)   │
                       └────────────┬────────────┘
                                    │
                         POST /v1/orders (paise)
                                    ▼
                       ┌─────────────────────────┐
                       │  Razorpay Payment Rails │
                       └─────────────────────────┘
```

---

## 2. Responsibility Division Matrix

| Responsibility Domain | Owned Exclusively By | Enforced Mechanism | Rationale |
| :--- | :--- | :--- | :--- |
| **Natural Language Parsing** | **LLM** | Prompt engineering + schema extraction | Natural language variations in buyer queries require semantic understanding. |
| **Intent Constraint Extraction** | **LLM** | Pydantic JSON Mode Output | Maps fuzzy buyer needs ("high pressure", "under 18k") to structured fields. |
| **Strategy Generation** | **LLM** | Candidate Generator Node | Creative bundling, qualitative framing, and value propositions. |
| **Qualitative Explanation** | **LLM** | Natural Language Output | Explains to merchants why a bundle was offered in human terms. |
| **Currency & Price Arithmetic** | **Deterministic Code** | Pure Python integer math (paise) | LLMs hallucinate calculations and roundoff errors. |
| **COGS & Margin Calculation** | **Deterministic Code** | Database lookups + arithmetic | Financial solvency cannot rely on model probabilities. |
| **Discount Ceiling Enforcement**| **Deterministic Code** | Hard numerical comparison | Prevents catastrophic loss-leader promotions. |
| **Buyer Budget Verification** | **Deterministic Code** | Integer inequality ($\text{Basket} \le \text{Budget}$) | Guarantees proposal is within buyer's stated maximum. |
| **Inventory Stock Check** | **Deterministic Code** | SQL `inventory_count >= qty` | Prevents overselling stock not on hand. |
| **Razorpay API Authentication** | **Deterministic Code** | Environment secrets in backend adapter | API secrets are never exposed to LLM context or client. |
| **Webhook Signature Check** | **Deterministic Code** | HMAC SHA256 byte verification | Cryptographic verification requires exact binary hashing. |
| **Event Deduplication** | **Deterministic Code** | Database uniqueness on `X-Razorpay-Event-Id` | Idempotency must be guaranteed by ACID transactions. |
| **Audit Logging** | **Deterministic Code** | Immutable SQL ledger | Regulatory and commercial auditing must be tamper-proof. |

---

## 3. Concrete Failure Scenarios & Deterministic Fencing

### Scenario 3.1: LLM Proposes Negative Margin
- *Hypothetical Flaw*: LLM attempts to win an aggressive AI buyer by pricing a ₹15,000 coffee maker at ₹7,000 (below its ₹8,000 COGS).
- *Deterministic Fencing*:
  ```python
  unit_cogs = product.cogs_paise
  gross_margin_pct = ((proposed_price - unit_cogs) / proposed_price) * 100
  if gross_margin_pct < merchant_config.global_margin_floor_pct:
      raise PolicyViolationError(
          f"Margin {gross_margin_pct:.1f}% violates floor {merchant_config.global_margin_floor_pct}%"
      )
  ```
- *Outcome*: Proposal is rejected immediately. The system falls back to the merchant's approved baseline catalog offer.

### Scenario 3.2: LLM Hallucinates Out-of-Stock SKU
- *Hypothetical Flaw*: LLM suggests bundling a discontinued premium tamper to increase perceived value.
- *Deterministic Fencing*:
  ```python
  if product.inventory_count < item.quantity:
      raise OutOfStockError(f"SKU {product.sku} has {product.inventory_count} units; {item.quantity} requested")
  ```
- *Outcome*: Proposal fails validation; audit record logged; agent falls back to single-product baseline.

### Scenario 3.3: LLM Hallucinates Non-Existent Discounts or Arithmetic Errors
- *Hypothetical Flaw*: LLM proposes item 1 at ₹14,000, item 2 at ₹3,000, discount ₹1,000, but outputs `total = 1500000` instead of `1600000`.
- *Deterministic Fencing*:
  ```python
  expected_total = sum(i.proposed_unit_price_paise * i.quantity for i in proposal.items) - proposal.bundle_discount_paise
  if proposal.total_proposed_price_paise != expected_total:
      # Deterministic engine overrides hallucinated total with true sum
      corrected_total = expected_total
  ```
- *Outcome*: Financial math is strictly recalculated by code. Zero reliance on LLM arithmetic.
