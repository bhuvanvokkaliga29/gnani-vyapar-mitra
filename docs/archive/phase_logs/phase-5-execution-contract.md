# Phase 5 Execution Contract: Deterministic Commercial Execution Gate

**Specification Version**: `execution-gate/v1`  
**Status**: ACTIVE & CONTRACT FROZEN  
**Inviolable Principle**: **THE LLM CAN PROPOSE. IT CANNOT SPEND.**

---

## 1. Architectural Overview

The Deterministic Commercial Execution Gate acts as the authoritative boundary between **AI-generated commercial policy proposals** and **financial transaction execution**.

```text
AI Buyer
   ↓
Buyer Intent Engine (Phase 3)
   ↓
BuyerIntent v1
   ↓
MerchantCommerceContext v1 (Phase 2)
   ↓
Merchant Policy Agent (Phase 4)
   ↓
PolicyProposal v1 (Provisional)
   ↓
PHASE 5 — DETERMINISTIC EXECUTION GATE
   ├── Fresh Merchant Database State Revalidation
   ├── Atomic Inventory Reservation
   └── Idempotency Ledger
   ↓
ExecutionAuthorization v1
   ↓
Razorpay Adapter (Phase 1)
   ↓
Razorpay Test-Mode Order
   ↓
Webhook / Reconciliation
   ↓
Verified Transaction State (PAID)
```

---

## 2. Revalidation Contract

A Phase 4 `PolicyProposal v1` is explicitly provisional (`is_provisional = True`).
Before any Razorpay order is authorized, the proposal must undergo fresh-state revalidation:

```text
PolicyProposal + Fresh MerchantCommerceContext (Direct DB)
                  ↓
          ExecutionValidator
```

### Deterministic Invariants Enforced

1. **Product Validity**:
   - Product exists in the current merchant catalog.
   - Product belongs to the matching merchant tenant (`merchants.id`).
   - Product `is_active` is True.
   - Product currency matches merchant currency.
   - Available-to-sell inventory (`inventory_quantity - reserved_quantity`) $\ge$ requested quantity.

2. **Commercial Economics Recalculation**:
   - Gross revenue calculated in exact integer paise from current product prices.
   - Promotional discount recomputed and capped by current merchant `maximum_discount_percent`.
   - Net revenue payable amount computed in integer paise:
     $$\text{net\_revenue} = \text{gross\_revenue} - \text{promotional\_discount}$$
   - Total COGS calculated from current product unit costs in paise.
   - Gross margin % recalculated using exact Decimal arithmetic.
   - Gross margin % must meet or exceed merchant `minimum_margin_percent`.
   - Net payable amount must satisfy buyer `max_amount_paise` (if budget constraint present).

3. **Proposal & Strategy Integrity**:
   - Policy version must equal `merchant-policy/v1`.
   - Candidate must exist in proposal candidate list with `CandidateValidationStatus.APPROVED`.
   - Strategy type `NO_OFFER` is **NEVER** authorized (rejected with `NO_EXECUTABLE_OFFER`).

---

### Single-Use Authorization Invariant

> [!IMPORTANT]
> **An `ExecutionAuthorization` authorizes exactly one business execution.**
> Once `ORDER_CREATED` or a terminal failure state is reached, the proposal cannot be reused to create another financial action under a new request.
> Replaying with the exact same idempotency key returns the cached idempotent execution (`is_duplicate = True`).
> Attempting to execute an already-completed proposal under a different attempt or key is strictly rejected with `EXECUTION_ALREADY_COMPLETED`.

---

## 3. Inventory Reservation Lifecycle

```text
       RESERVED (Atomically on EXECUTION_AUTHORIZED)
          │
          ▼
    ORDER_CREATED (Razorpay Test Mode Order Created)
          │
    ┌─────┴────────────────────────────────┐
    ▼                                      ▼
payment.captured                     payment.failed /
(Webhook)                            cancelled / expired
    │                                      │
    ▼                                      ▼
CONSUME & SETTLE                        RELEASE
inventory_quantity -= qty           reserved_quantity -= qty
reserved_quantity  -= qty           (Stock fully restored)
(Transaction PAID)                  (Zero phantom leaks)
```

Guarantees that `reserved_quantity` NEVER leaks or stays permanently $>0$ after an unpaid, failed, or expired checkout attempt.

---

## 4. Execution State Machine

```text
PROPOSAL_RECEIVED
       ↓
  REVALIDATING
   ┌───┴───────────────────────┐
   ▼                           ▼
REJECTED             EXECUTION_AUTHORIZED
                               ↓
                      ORDER_CREATE_PENDING
                               ↓
                         ORDER_CREATED
                               ↓
                        AWAITING_PAYMENT
                               ↓
                              PAID
```

Failure states:
- `ORDER_CREATE_FAILED`: Razorpay API call failed; inventory reservation safely rolled back.
- `RECONCILIATION_REQUIRED`: Network timeout during order creation; reconciled via provider GET.
- `PAYMENT_FAILED`: Razorpay webhook indicates payment failure; reserved inventory released.
- `EXPIRED` / `CANCELLED`: Checkout window expired or cancelled; reserved inventory released.

---

## 5. ExecutionAuthorization DTO

```json
{
  "authorization_id": "auth_abc123456789",
  "proposal_id": "prop_test_01",
  "merchant_id": "merch_atlas",
  "candidate_id": "cand_single_pack",
  "authorized_amount_paise": 480000,
  "currency": "INR",
  "status": "EXECUTION_AUTHORIZED",
  "rejection_reasons": [],
  "recalculated_economics": {
    "gross_revenue_paise": 500000,
    "promotional_discount_paise": 20000,
    "net_revenue_paise": 480000,
    "total_cogs_paise": 250000,
    "gross_profit_paise": 230000,
    "gross_margin_percent": 47.92,
    "effective_discount_percent": 4.00,
    "is_compliant": true
  },
  "receipt": "rcpt_78df8b12_cand_sin",
  "idempotency_key": "idem_merch_atlas_prop_test_01_cand_single_pack",
  "validation_version": "execution-gate/v1",
  "source_policy_version": "merchant-policy/v1",
  "context_snapshot_timestamp": "2026-09-03T00:30:00Z",
  "authorized_at": "2026-09-03T00:30:05Z"
}
```

---

## 5. Machine-Readable Rejection Taxonomy

| Rejection Code | Trigger Condition |
|:---|:---|
| `PROPOSAL_NOT_FOUND` | Proposal ID or selected candidate ID not found |
| `MERCHANT_MISMATCH` | Proposal merchant does not match requested tenant |
| `INVALID_PROPOSAL_STATUS` | Candidate not approved or proposal status invalid |
| `NO_EXECUTABLE_OFFER` | Strategy is `NO_OFFER` |
| `STALE_CONTEXT` | Context drifted beyond tolerable execution bounds |
| `PRODUCT_UNAVAILABLE` | SKU missing or marked inactive |
| `OUT_OF_STOCK` | Available-to-sell inventory is less than required quantity |
| `PRICE_CHANGED` | Price updated in DB |
| `COST_CHANGED` | COGS updated in DB |
| `MARGIN_TOO_LOW` | Recalculated margin falls below `minimum_margin_percent` |
| `DISCOUNT_TOO_HIGH` | Requested discount exceeds `maximum_discount_percent` |
| `OVER_BUDGET` | Recalculated price exceeds buyer budget ceiling |
| `BUYER_REQUIREMENT_CHANGED` | Fresh product attributes violate buyer hard requirements |
| `BUYER_EXCLUSION_VIOLATED` | Fresh product contains buyer-excluded attributes |
| `RELATIONSHIP_INVALID` | Bundle component relationship missing in fresh catalog |
| `CURRENCY_MISMATCH` | Product currency does not match merchant base currency |
| `CONCURRENCY_CONFLICT` | Atomic inventory reservation race lost |
| `EXECUTION_ALREADY_COMPLETED` | Execution record already completed |
| `IDEMPOTENCY_CONFLICT` | Duplicate submission with incompatible payload |
| `RAZORPAY_ORDER_CREATION_FAILED` | Upstream Razorpay order creation returned an error |
| `RECONCILIATION_REQUIRED` | Network timeout during order creation |
