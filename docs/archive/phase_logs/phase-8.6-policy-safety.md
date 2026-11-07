# Phase 8.6 Technical Specification: Deterministic Policy Safety & Admissibility Gate

**Contract Version**: `policy-safety/v1`  
**Status**: **COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN**  
**Core Invariant**: **LEARNING SCORE CANNOT OVERRIDE HARD SAFETY; FRESH STATE REVALIDATION ONLY; ZERO EXECUTION AUTHORITY; ZERO POLICY MUTATION**

---

## 1. Purpose & Core Objective

Phase 8.6 introduces the **deterministic safety and admissibility firewall** (`policy-safety/v1`).
It answers a single binary question for a single candidate policy proposal:
$$\boxed{\text{"Is this proposed policy currently admissible under the merchant's authoritative, fresh commercial state and all applicable hard constraints?"}}$$

The gate returns:
- `ADMISSIBLE`
- `REJECTED` (with deterministic, machine-readable failure codes)

Phase 8.6 is a pure safety firewall. It does **not** rank candidates, does **not** learn, does **not** explore, does **not** promote, and does **not** execute transactions.

---

## 2. Core Safety Invariant: Learning Score Cannot Override Hard Safety

A policy with:
- High predicted contribution
- High historical performance
- High UCB
- High strategy priority

**MUST still be rejected** if it violates any authoritative merchant constraint.

```text
Learned Candidate Proposal (Phase 8.5)
                  ↓
Deterministic Safety Gate (Phase 8.6)
       [Evaluates Fresh DB State]
                  ↓
          ALLOW or REJECT
                  ↓
Phase 5 Execution Gate (Re-evaluates & executes)
```

Learning models are never permitted to bypass merchant guardrails, price floors, discount ceilings, or inventory constraints.

---

## 3. Fresh Authoritative State Requirement

A candidate selection from Phase 8.5 is a snapshot in time. Authoritative merchant conditions (catalog prices, inventory, constraints) can change between selection and validation.
Phase 8.6 always reloads fresh `MerchantCommerceContext` from the primary database before evaluation:
- Never trusts caller-supplied prices, margins, COGS, discounts, or inventory levels.
- Recomputes unit economics in integer paise against fresh product costs and prices.
- Validates available-to-sell inventory (`inventory_quantity - reserved_quantity`).

---

## 4. Policy Identity & Scope

- **Merchant Scope**: The candidate policy must belong to the authenticated merchant. Cross-tenant policy evaluation is strictly forbidden.
- **Policy Version**: Validates policy version (e.g., `merchant-policy/v1`).
- **Opportunity Identity**: Preserves canonical `opportunity_id` for decision tracing.

---

## 5. Economic Revalidation & Hard Constraints

Phase 8.6 deterministically recomputes:
- `gross_revenue_paise = sum(price * qty)`
- `promotional_discount_paise = round(gross_revenue * discount_pct / 100)`
- `net_revenue_paise = gross_revenue - promotional_discount`
- `total_cogs_paise = sum(cost * qty)`
- `gross_profit_paise = net_revenue - total_cogs`
- `gross_margin_percent = (gross_profit / net_revenue) * 100`

### Hard Guardrail Checks:
1. **Discount Ceiling**: `discount_percent <= merchant.maximum_discount_percent` (failure code: `DISCOUNT_LIMIT_EXCEEDED`).
2. **Contribution / Margin Floor**: `gross_margin_percent >= merchant.minimum_margin_percent` (failure code: `CONTRIBUTION_FLOOR_VIOLATED`).
3. **Buyer Budget Ceiling**: `net_revenue_paise <= buyer_intent.budget.max_amount_paise` (failure code: `BUDGET_LIMIT_EXCEEDED`).

---

## 6. Inventory Safety & Bundles

- For single products: `available_to_sell >= required_quantity`.
- For bundles: every required component must have `available_to_sell >= required_quantity`.
- Bundle relationship check: bundle components must have verified `COMPLEMENTARY` or `BUNDLE_COMPONENT` affinity relationships in `fresh_context.relationships`.
- Failure code: `INVENTORY_INSUFFICIENT` or `RELATIONSHIP_INVALID`.

---

## 7. Baseline `NO_OFFER` Safety

The reserve baseline `NO_OFFER` is safe by definition:
- It requires no product catalog presence or inventory reservation.
- It generates 0 revenue, 0 discount, 0 cost, 0 profit.
- It returns `ADMISSIBLE` with reason `"ADMISSIBLE_ALL_CONSTRAINTS_SATISFIED"` (unless structural or merchant scope errors are present).

---

## 8. Deterministic Failure Ordering

When multiple constraints fail simultaneously, failure codes are sorted deterministically according to the canonical domain priority:

| Priority | Failure Code | Description |
|:---:|:---|:---|
| 1 | `MERCHANT_SCOPE_MISMATCH` | Candidate references mismatch merchant context |
| 2 | `POLICY_NOT_FOUND` | Empty or missing candidate ID |
| 3 | `INVALID_POLICY` | Candidate validation_status is REJECTED |
| 4 | `POLICY_VERSION_INVALID` | Incompatible policy version string |
| 5 | `VERSION_INCOMPATIBLE` | Request safety_version != policy-safety/v1 |
| 6 | `STALE_CONTEXT` | Merchant or commerce context not found in DB |
| 7 | `PRODUCT_NOT_FOUND` | Referenced product not in merchant catalog |
| 8 | `PRODUCT_INELIGIBLE` | Inactive product, currency mismatch, or exclusion hit |
| 9 | `RELATIONSHIP_INVALID` | Bundle components lack verified affinity relationship |
| 10 | `INVENTORY_INSUFFICIENT` | Component available_to_sell < requested quantity |
| 11 | `DISCOUNT_LIMIT_EXCEEDED` | Discount % exceeds merchant maximum |
| 12 | `CONTRIBUTION_FLOOR_VIOLATED` | Gross margin % below merchant floor |
| 13 | `BUDGET_LIMIT_EXCEEDED` | Net revenue exceeds buyer's max budget |
| 14 | `ECONOMICS_RECALCULATION_FAILED` | Arithmetic failure during recomputation |

The primary `validation_reason` is always `failure_codes[0].value`.

---

## 9. Execution Boundary & Relationship to Phase 5

$$\boxed{\text{ADMISSIBLE} \ne \text{EXECUTION\_APPROVED}}$$

- Phase 8.6 does **NOT** authorize execution.
- Phase 8.6 does **NOT** reserve inventory.
- Phase 8.6 does **NOT** create Razorpay orders.
- Phase 8.6 does **NOT** call Razorpay APIs.
- Phase 5 remains the sole commercial execution gate, performing transactional locking, atomic inventory reservation, and Razorpay Test Mode checkout order creation.

---

## 10. Auditability & State-Aware Idempotency (Phase 8.6.1 Refinement)

- **State-Aware Idempotency**:
  - Idempotency is keyed on: `(merchant_id, opportunity_id, policy_id, policy_version, authoritative_state_fingerprint)`.
  - When authoritative merchant state (inventory, price, cost, constraints) has **not** changed: repeated requests for the same opportunity return the cached idempotent check.
  - When authoritative merchant state **has** changed (e.g., inventory drops from 10 to 0): the fingerprint changes, forcing a fresh revalidation against the primary DB state.
- **Immutable Historical Audit Records**:
  - Every revalidation creates a new `PolicySafetyRecord` (`safe_...`) in `policy_safety_records` without overwriting the previous evaluation.
  - Both the historical check at $T_1$ and the revalidated check at $T_2$ are preserved immutably for full forensic auditability.
- **Tenant Isolation**:
  - Read endpoint `GET /api/v1/policy-safety/{check_id}?merchant_id={merchant_id}` strictly enforces cross-tenant access rejection (HTTP 403).

