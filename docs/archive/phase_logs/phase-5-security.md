# Phase 5 Security Architecture & Threat Model

## 1. Core Invariant & Boundary Enforcement

> **THE LLM CAN PROPOSE. IT CANNOT SPEND.**

The LLM exists entirely within Phase 4 (`MerchantPolicyAgent`). In Phase 5:
- **Zero LLM Credentials**: The LLM is provided zero Razorpay API keys or secrets.
- **Zero Network Handles**: The LLM cannot make outbound HTTP requests.
- **Zero Spending Capability**: All monetary amounts are computed server-side in Python. Client- or LLM-supplied prices are strictly ignored.
- **Deterministic Gatekeeper**: Only the deterministic `ExecutionValidator` and `ExecutionGate` can authorize orders.

---

## 2. Threat Vector Mitigation

### Vector 1: Client Financial Amount Tampering
- **Attack**: An attacker sends `POST /api/v1/policy/execute` with `{"amount_paise": 100}` to purchase an ₹80,000 product for ₹1.
- **Mitigation**:
  - `PolicyExecuteRequest` strictly forbids extra fields (`ConfigDict(extra="forbid")`), rejecting the request with HTTP 422.
  - The payable amount is recalculated strictly from server-side database records.
- **Verification**: `test_client_amount_tampering_strictly_forbidden` (PASSED).

### Vector 2: Cross-Tenant Execution & Merchant Spoofing
- **Attack**: A merchant attempts to execute an order against another merchant's catalog or policy proposal.
- **Mitigation**:
  - Proposal merchant ID must match request merchant ID.
  - All product IDs in the candidate are verified against the target merchant's database records.
  - Any mismatch immediately triggers `MERCHANT_MISMATCH` with zero Razorpay calls.
- **Verification**: `test_cross_tenant_execution_blocked` (PASSED).

### Vector 3: Execution of Rejected or NO_OFFER Strategies
- **Attack**: A malicious client captures a `NO_OFFER` or `REJECTED` candidate ID and attempts to force execution.
- **Mitigation**:
  - `candidate.validation_status` must equal `APPROVED`.
  - `candidate.strategy_type` cannot equal `NO_OFFER` (rejected with `NO_EXECUTABLE_OFFER`).
- **Verification**: `test_rejected_candidate_cannot_execute` and `test_no_offer_strategy_cannot_execute` (PASSED).

### Vector 4: Stale State Exploitation
- **Attack**: A buyer uses an old proposal for an item whose price has increased or whose stock has dropped to zero.
- **Mitigation**:
  - Proposal is advisory (`is_provisional = True`).
  - Fresh stock and prices are fetched from the database immediately prior to authorization.
- **Verification**: `test_stale_inventory_rejected_from_execution` (PASSED).

### Vector 5: Inventory Race Conditions (Double-Spend)
- **Attack**: Two concurrent execution requests attempt to claim the last unit of scarce inventory (`stock = 1`).
- **Mitigation**:
  - Atomic conditional update: `UPDATE products SET reserved_quantity = reserved_quantity + :qty WHERE (inventory_quantity - reserved_quantity) >= :qty`.
  - Exactly one request increments reserved stock; the competing request receives 0 affected rows and fails with `CONCURRENCY_CONFLICT` / `OUT_OF_STOCK`.
- **Verification**: `test_atomic_reservation_race_stock_one` (PASSED).

### Vector 6: Razorpay Test-Mode Isolation
- **Defense**: Credentials must use `rzp_test_` prefix. Live keys are rejected at startup.
