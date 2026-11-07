# Failure-Injection & Chaos Testing Specification

This document defines the automated chaos testing suite and negative scenario assertions designed to prove that the system fails safely, deterministically, and visibly under stress.

---

## 1. Failure-Injection Philosophy

A production-grade agentic financial system is defined not by how it behaves on the "happy path", but by **how safely it halts when dependencies fail**.
Every failure-injection test asserts three invariant conditions:
1. **Safety**: No invalid financial order is dispatched to Razorpay.
2. **Deterministic State**: Database state remains consistent (no half-committed records).
3. **Auditability**: An explicit audit entry records the exact reason for rejection or fallback.

---

## 2. Chaos Scenario Test Suite

### Test Case 1: Malformed / Non-JSON LLM Output
- **Injection**: Mock LLM client returns arbitrary text (e.g., `"I think you should buy the coffee machine for a great discount!"`).
- **Assertion**:
  - Pydantic schema validation raises `ValidationError`.
  - Strategy Generator node catches error and routes to fallback baseline.
  - Fallback offer (single SKU at catalog price) is returned.
  - Audit log records `error_type: PARSE_ERROR`.

### Test Case 2: Negative Margin Proposal
- **Injection**: Mock LLM proposes core product (COGS: ₹8,000) at ₹6,500 to aggressively convert a price-sensitive buyer.
- **Assertion**:
  - Deterministic Policy Engine evaluates `Gross Margin % = -23.0%`.
  - Condition `Gross Margin % >= Margin Floor % (25%)` evaluates to `FALSE`.
  - Proposal is flagged `REJECTED`.
  - Zero Razorpay API calls are dispatched.
  - Response returns standard baseline catalog pricing.

### Test Case 3: Discount Ceiling Breach
- **Injection**: Mock LLM proposes a 40% discount bundle when merchant's `max_discount_ceiling_pct` is set to 20%.
- **Assertion**:
  - Deterministic Policy Engine calculates effective discount = 40.0%.
  - Gate 2 check fails (`ERR_DISCOUNT_CEILING_EXCEEDED`).
  - Proposal rejected; baseline offer served; audit event persisted.

### Test Case 4: Out-of-Stock SKU Bundling
- **Injection**: Mock LLM suggests bundling an accessory with `inventory_count = 0`.
- **Assertion**:
  - Inventory check flags item as unavailable.
  - Proposal fails validation; engine triggers bundle adjustment or falls back to single in-stock item.
  - No oversold order is created.

### Test Case 5: Razorpay Gateway Timeout
- **Injection**: Mock HTTP client raises `httpx.TimeoutException` on `POST /v1/orders`.
- **Assertion**:
  - Adapter does **not** re-invoke `POST /v1/orders`.
  - Adapter executes reconciliation check querying order store by `receipt = decision_id`.
  - Order status is set to `PENDING_RECONCILIATION`.
  - Merchant UI displays pending reconciliation banner.

### Test Case 6: Duplicate Webhook Event Ingestion
- **Injection**: Send the exact same webhook payload twice with identical `X-Razorpay-Event-Id` and valid signature.
- **Assertion**:
  - First request returns HTTP 200 and records order as `PAID`.
  - Second request triggers unique constraint catch on `processed_webhook_events`.
  - Second request immediately returns HTTP 200 with `status: already_processed`.
  - Transaction metrics and policy bandit weights are incremented **exactly once**.

### Test Case 7: Missing / Delayed Webhook (API Reconciliation Fallback)
- **Injection**: Test payment is marked captured in Razorpay, but webhook delivery is simulated as dropped.
- **Assertion**:
  - Background reconciliation job calls `GET /v1/orders/{id}/payments`.
  - Reconciler discovers captured payment, updates internal order to `PAID`, and triggers policy learning update.

### Test Case 8: Database Connection Interruption
- **Injection**: PostgreSQL connection drops during transaction commit of an approved decision.
- **Assertion**:
  - Transaction rollbacks cleanly.
  - No orphaned Razorpay order is created.
  - API returns HTTP 503 Service Unavailable.

### Test Case 9: Complete Model Downtime
- **Injection**: LLM provider returns HTTP 503 / connection refused.
- **Assertion**:
  - System logs `MODEL_UNAVAILABLE`.
  - System instantly serves static catalog baseline without user-facing crash.
  - Merchant operations continue uninterrupted.
