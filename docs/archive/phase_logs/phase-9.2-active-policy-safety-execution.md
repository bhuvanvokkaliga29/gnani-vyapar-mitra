# Phase 9.2: Active Policy + Safety + Execution Boundary

**Contract Version**: `execution-boundary/v1`  
**Status**: `VERIFIED & FROZEN`  
**Test Suite**: 19 passed (Phase 9.2), 655 passed (Full Repository Regression)

---

## 1. Executive Summary & Purpose

Phase 9.2 implements the governed runtime execution boundary separating canonical decision evaluations (Phase 9.1) from transactional execution in Phase 5 and Razorpay.

The primary user promise of the Merchant Policy Agent is:
> **"Teach an AI what makes your business win."**

And the core governing axiom remains:
> **"LLM CAN PROPOSE. CODE VALIDATES. CODE EXECUTES. RAZORPAY REPORTS. AGENT LEARNS."**

Phase 9.1 definitively produces an immutable `DecisionEnvelope` representing the canonical commercial decision. Crucially, Phase 9.1 **never authorizes execution** (`execution_authorized = False`, `execution_status = "PENDING_EXECUTION_GATE"`). 

Phase 9.2 acts as the authoritative gatekeeper determining:
1. Whether the selected policy is still the merchant's valid active policy (under Phase 8.8 `PolicyLifecycleService` authority).
2. Whether the decision is admissible under fresh authoritative merchant state (under Phase 2 `CommerceService` and Phase 8.6 `PolicySafetyService` authority).
3. Whether the decision is eligible to cross into transactional execution.
4. If eligible, issues a single-use server-generated authorization token and hands off to the existing Phase 5 `ExecutionGate` to reserve inventory and create a Razorpay Test Mode order.

---

## 2. Architecture & Authority Chain

```
                   Phase 9.1 Canonical Decision Envelope
                                   ↓
                   Phase 9.2 DecisionExecutionBoundaryService
                                   ↓
        [Step 1] Merchant Verification & Tenant Isolation Check
                                   ↓
        [Step 2] Boundary Idempotency Ledger Lookup (decision_executions)
                 └─ If existing: Replay cached response (is_duplicate=True)
                                   ↓
        [Step 3] Freshness TTL Verification (elapsed <= ttl_seconds)
                 └─ If stale: Reject with DECISION_STALE (Fail-Closed)
                                   ↓
        [Step 4] Active Policy / Lifecycle Verification (Phase 8.8 Authority)
                 ├─ If retired: Reject with POLICY_RETIRED
                 ├─ If rolled back: Reject with POLICY_ROLLED_BACK
                 └─ If active policy mismatch in exploit: Reject with POLICY_NOT_ACTIVE
                                   ↓
        [Step 5] Fresh State Retrieval & Fingerprinting (Phase 2 & 8.6)
                 ├─ Reload fresh MerchantCommerceContext
                 └─ Compute state fingerprint (SHA-256)
                                   ↓
        [Step 6] Commercial Safety Re-evaluation (Phase 8.6 PolicySafetyService)
                 └─ If not ADMISSIBLE: Reject with SAFETY_REJECTED (Fail-Closed)
                                   ↓
        [Step 7] Single-Use Server Authorization Token Issued (eauth_...)
                 └─ Authoritative payable amount derived from recalculated economics
                                   ↓
        [Step 8] Safe Handoff to Phase 5 ExecutionGate
                 ├─ Atomic Inventory Reservation (InventoryReservationManager)
                 └─ Provider Order Creation (OrderService / Razorpay Test Mode)
                                   ↓
        [Step 9] Boundary Audit Ledger Persistence (decision_executions)
                 └─ Zero writes to learning evidence, memory, or bandit models!
                                   ↓
        [Step 10] Return Customer-Safe DecisionExecuteResponse
```

---

## 3. Strict Boundary Invariants

1. **Non-Authorization Invariant (9.1 vs 9.2)**:
   - Phase 9.1 decisions strictly evaluate proposals; they never execute or authorize execution.
   - Phase 9.2 is the sole authority issuing `authorization_id` tokens and calling Phase 5.
2. **No Client Financial Authority**:
   - Callers cannot specify `authorized_amount_paise`, discount percentages, or safety overrides.
   - All financial amounts are derived server-side from authoritative catalog and margin constraints.
3. **Fail-Closed Execution**:
   - Any failure (stale TTL, inactive merchant, retired/rolled back policy, stockout, margin breach) immediately aborts boundary traversal before touching Phase 5 or Razorpay.
4. **Single-Use Authorization & Idempotency**:
   - Each decision can only be executed once.
   - Repeated calls look up the boundary execution ledger and replay the prior execution record with `is_duplicate=True`, guaranteeing zero duplicate Razorpay orders.
5. **No Learning Side Effects in 9.2**:
   - Phase 9.2 traversal generates zero rows in `learning_evidence_records` or `policy_memories`, and leaves bandit weights untouched. Closed-loop learning is deferred to Phase 9.3 upon observed payment/telemetry settlement.
6. **Information Hygiene**:
   - `DecisionExecuteResponse` strictly strips all merchant confidential financial economics (`cogs_paise`, `gross_margin_percent`, `gross_profit_paise`, `ucb_score`).

---

## 4. API Endpoints

### 1. Execute Canonical Decision
- **Endpoint**: `POST /api/v1/decisions/{decision_id}/execute`
- **Request Body**:
  ```json
  {
    "merchant_id": "merch_atlas_travel",
    "idempotency_key": "optional_client_key"
  }
  ```
- **Response** (`execution-boundary/v1`):
  ```json
  {
    "execution_id": "dexec_7efb14985079",
    "decision_id": "dec_7efb14985079",
    "merchant_id": "merch_atlas_travel",
    "opportunity_id": "opp_travel_001",
    "boundary_status": "EXECUTION_COMPLETED",
    "execution_authorized": true,
    "authorization_id": "eauth_86426a9454ae4438",
    "safety_check_id": "safe_de0c738764ed",
    "phase5_execution_id": "exec_5d7764d84f93",
    "order_id": "order_a2f840901df6",
    "razorpay_order_id": "order_RZPTEST123456",
    "authorized_amount_paise": 475000,
    "currency": "INR",
    "rejection_reasons": [],
    "is_duplicate": false,
    "executed_at": "2026-09-03T20:10:08.520000Z",
    "boundary_version": "execution-boundary/v1"
  }
  ```

### 2. Retrieve Boundary Execution
- **Endpoint**: `GET /api/v1/decisions/{decision_id}/execution?merchant_id={merchant_id}`
- **Response**: Returns identical `DecisionExecuteResponse` from immutable audit record.

---

## 5. Adversarial Hardening & Verified Attack Vectors

The suite in `tests/integration/test_execution_boundary_adversarial.py` verifies 10 distinct failure modes and attack vectors:

| Attack Vector | Simulated Scenario | Boundary Defense | Outcome |
| :--- | :--- | :--- | :--- |
| **Client Authority Injection** | Client supplies forged `authorized_amount_paise` | Schema validator rejects (`extra="forbid"`) | Validation Error (HTTP 422) |
| **Client Token Injection** | Client supplies forged `authorization_id` | Schema validator rejects (`extra="forbid"`) | Validation Error (HTTP 422) |
| **Cross-Tenant Attack** | Merchant Beta requests execution of Merchant Alpha's decision | Tenant scope validation | `DecisionTenantViolationError` (HTTP 403) |
| **Stale Decision Attack** | Execution attempted past 900s validity window | Timezone-aware TTL freshness calculation | Fails closed with `DECISION_STALE` |
| **Policy Retired Race** | Policy was active at 9.1 decision, but retired in 8.8 prior to execution | Phase 8.8 version audit check | Fails closed with `POLICY_RETIRED`, 0 orders |
| **Policy Rollback Race** | Policy was active at 9.1 decision, but rolled back in 8.8 prior to execution | Phase 8.8 version audit check | Fails closed with `POLICY_ROLLED_BACK`, 0 orders |
| **Inventory Exhaustion Race** | Inventory drops to 0 after 9.1 decision | Phase 8.6 safety gate re-evaluates fresh state | Rejects with `INVENTORY_INSUFFICIENT`, 0 orders |
| **Margin Floor Breach Race** | Product COGS increases after 9.1 decision | Phase 8.6 safety gate re-evaluates fresh state | Rejects with `CONTRIBUTION_FLOOR_VIOLATED`, 0 orders |
| **Learning Side Effect Attack** | Phase 9.2 execution attempted | Database counts on learning evidence & memory | Zero rows added to `learning_evidence_records` |
| **Information Leakage Attack** | Serialized response inspected | Schema excludes private fields | Zero `cogs_paise` or `gross_margin_percent` |

---

## 6. Verification Results

- **Phase 9.2 Unit Tests**: 9 passed
- **Phase 9.2 Integration Tests**: 3 passed
- **Phase 9.2 Adversarial Invariant Tests**: 7 passed
- **Full Repository Test Suite**: **655 passed, 0 failures (100%)**
