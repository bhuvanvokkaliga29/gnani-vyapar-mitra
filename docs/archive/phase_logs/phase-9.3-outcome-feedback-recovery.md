# Phase 9.3: Outcome, Feedback & Recovery Loop

## 1. Overview & Purpose

Phase 9.3 establishes the **Outcome, Feedback & Recovery Loop** (`outcome-feedback/v1`) for the Merchant Policy Agent. It directly reconnects the operational execution runtime (Phase 9.1 Canonical Decision Runtime and Phase 9.2 Active Policy & Safety Execution Boundary) with the autonomous policy learning system (Phase 8.1 Evidence, Phase 8.2 Reward, Phase 8.3 Memory, and Phase 8.4 Contextual LinUCB Model).

```
Operational Execution (9.2)
         ↓
Phase 5 Authoritative Transaction Truth (Orders & Payments)
         ↓
Outcome Resolution & Mapping (9.3)
         ↓
Learning Eligibility Firewall (blocks ORDER_CREATED, UNRESOLVED)
         ↓
Phase 8.1 Learning Evidence Ingestion
         ↓
Phase 8.2 Reward Signal Evaluation (Contribution = Revenue - COGS)
         ↓
Phase 8.3 Policy Memory Persistence (Idempotent Append-Only)
         ↓
Phase 8.4 Contextual LinUCB Model Update (Idempotent Exactly-Once)
```

---

## 2. Core Architectural Ownership Rules

Phase 9.3 acts strictly as an **orchestration and feedback layer**. It adheres to these architectural boundaries:
- **Phase 5 Ownership**: Phase 5 owns the local transaction state machine (`TransactionState`), inventory deduction/release, and Razorpay API/webhook verification. Phase 9.3 does not duplicate this state machine.
- **Provider Truth**: The server checks internal database state and Razorpay provider truth. Clients have **zero authority** over transaction amounts, payment success flags, or rewards.
- **Phase 8.1 Evidence**: Phase 8.1 owns evidence validation and eligibility determination (`PolicyLearningEvidence`).
- **Phase 8.2 Reward**: Phase 8.2 owns deterministic gross contribution calculation ($Contribution = RealizedRevenue - RealizedCOGS$).
- **Phase 8.3 Memory**: Phase 8.3 owns immutable historical memory records with lineage and supersession.
- **Phase 8.4 Learning**: Phase 8.4 owns the Contextual LinUCB algorithm, feature extraction ($x \in \mathbb{R}^{19}$), and optimistic concurrency model persistence.

---

## 3. Semantic State Mapping

Phase 5 `TransactionState` is mapped deterministically to `outcome-feedback/v1` `OutcomeStatus`:

| Phase 5 `TransactionState` | Meaning / State | Semantic `OutcomeStatus` | Is Terminal? | Learning Eligible? | Economic Reward |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CREATION_PENDING` | Order pre-allocated in DB | `PENDING` | No | No (Blocked) | N/A |
| `ORDER_CREATED` | Order created with Razorpay | `ORDER_CREATED` | No | No (Blocked) | N/A |
| `UNCERTAIN` | Outbound Razorpay timeout | `UNRESOLVED` | No | No (Blocked) | N/A |
| `PAYMENT_PENDING` | Buyer at checkout | `PENDING` | No | No (Blocked) | N/A |
| `AUTHORIZED` | Payment authorized | `PENDING` | No | No (Blocked) | N/A |
| `CAPTURED` | Payment captured | `PAYMENT_SUCCESS` | Yes | Yes | $RealizedRev - COGS$ |
| `PAID` | Order fully paid | `PAYMENT_SUCCESS` | Yes | Yes | $RealizedRev - COGS$ |
| `FAILED` | Payment failed | `PAYMENT_FAILED` | Yes | Yes (Non-purchase) | $0\text{ paise}$ |
| `CANCELLED` | Order/payment cancelled | `PAYMENT_CANCELLED` | Yes | Yes (Non-purchase) | $0\text{ paise}$ |
| `FINALIZED` | Transaction settled | `PAYMENT_SUCCESS` | Yes | Yes | $RealizedRev - COGS$ |

---

## 4. Learning Eligibility Firewall

The Learning Eligibility Firewall guarantees that non-terminal, unverified, or ambiguous events **never** contaminate the learning model:
1. **`ORDER_CREATED` is NOT `PAYMENT_SUCCESS`**: Creating an order indicates intent to pay, not completed economic value. It is recorded as non-terminal, yielding zero evidence rows and zero model weight adjustments.
2. **`UNRESOLVED` is NEVER learning eligible**: Network timeouts or uncertain reconciliation states remain unresolved until provider confirmation.
3. **`CLIENT_REPORTED_SUCCESS` is rejected**: The `OutcomeProcessRequest` schema enforces `extra="forbid"`, preventing clients from passing amounts, payment status, or rewards.
4. **Denominator Preservation for Failed/Cancelled Payments**: Terminal payment failures are included in the denominator with $0\text{ paise}$ contribution to prevent survivor bias in policy evaluation.

---

## 5. Idempotent Exactly-Once Learning Effect

Under network retries, worker crashes, or duplicate webhooks, the system achieves **at-least-once feedback processing with idempotent exactly-once learning effect**:
1. **Deduplication at Execution Boundary**: `outcome_feedbacks` table enforces `UNIQUE(merchant_id, execution_id)`.
2. **Phase 8.3 Memory Idempotency**: Memory records enforce `UNIQUE(idempotency_key)` on `mem_{evidence_id}`.
3. **Model Update Flag**: `OutcomeFeedbackRecord.model_updated` is tracked explicitly. Model weights are updated once, and replayed requests skip algorithm updating.
4. **Optimistic Concurrency Control**: `PolicyLearningModelService.save_model` verifies `version == expected_version` to prevent lost updates under concurrency.

---

## 6. Information Hygiene Invariant

Customer-facing API responses (`OutcomeProcessResponse`) strictly exclude merchant internal unit economics:
- `cogs_paise`: Excluded
- `gross_margin_percent`: Excluded
- `model_weights` / `ucb_scores`: Excluded
- Safe public fields: `outcome_id`, `execution_id`, `decision_id`, `outcome_status`, `realized_revenue_paise`, `reward_contribution_paise`, `is_terminal`.

---

## 7. API Endpoints

- `POST /api/v1/outcomes/process`
- `GET /api/v1/outcomes/{outcome_id}`
- `GET /api/v1/executions/{execution_id}/outcome`
- Webhook auto-hook: When Razorpay triggers `order.paid`, `payment.captured`, or `payment.failed`, `WebhookService` invokes `OutcomeFeedbackService.process_webhook_outcome`.

---

## 8. Test Verification Summary

- Total Phase 9.3 Tests: **18 passed**
  - `tests/unit/test_outcome_feedback_schemas.py`: 4 passed
  - `tests/unit/test_outcome_feedback_service.py`: 5 passed
  - `tests/integration/test_outcome_feedback_integration.py`: 5 passed
  - `tests/integration/test_outcome_feedback_adversarial.py`: 4 passed
- Total Repository Tests: **673 passed**, 0 failures across 31 test files.
