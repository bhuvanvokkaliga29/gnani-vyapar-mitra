# Phase 1: Transaction State Machine Specification

This document defines the transaction state transitions, valid/invalid events, persistence behavior, and audit records for the **Merchant Policy Agent**.

---

## 1. Transaction State Topology

```text
[CREATION_PENDING]
        │
        ├── (POST /v1/orders succeeds) ──> [ORDER_CREATED]
        │                                         │
        │                                         ├── (Payment authorized) ──> [AUTHORIZED]
        │                                         │                                │
        │                                         ├── (Payment captured) ──────────┼──> [CAPTURED / PAID]
        │                                         │                                │           │
        │                                         └── (Payment failed) ──> [FAILED]            └── (Finalized) ──> [FINALIZED]
        │
        └── (Network Timeout / Failure) ──> [UNCERTAIN]
                                                │
                                                └── (Reconciliation resolves) ──> [ORDER_CREATED] or [FAILED]
```

---

## 2. State Transition Table

| Previous State | Triggering Event | Next State | Validity | Persistence Behavior | Generated Audit Event |
| :--- | :--- | :--- | :---: | :--- | :--- |
| *None* | `order_create_request` | `CREATION_PENDING` | VALID | Insert new `Order` row with `status='CREATION_PENDING'`, internal `decision_id`, generated `receipt`. | `order_creation_requested` |
| `CREATION_PENDING` | `razorpay_order_created` | `ORDER_CREATED` | VALID | Update `Order` with `razorpay_order_id`, set `status='ORDER_CREATED'`. | `order_creation_succeeded` |
| `CREATION_PENDING` | `gateway_timeout` | `UNCERTAIN` | VALID | Set `status='UNCERTAIN'`; schedule or trigger reconciliation. | `order_creation_timeout` |
| `UNCERTAIN` | `reconciliation_order_found` | `ORDER_CREATED` | VALID | Associate `razorpay_order_id` from API; update `status='ORDER_CREATED'`. | `order_reconciliation_completed` |
| `UNCERTAIN` | `reconciliation_not_found` | `FAILED` | VALID | Set `status='FAILED'`. Allow safe retry with fresh decision ID. | `order_reconciliation_failed` |
| `ORDER_CREATED` | `webhook:payment.authorized` | `AUTHORIZED` | VALID | Update `Order.status='AUTHORIZED'`. Insert `Payment` row. | `payment_state_updated` |
| `ORDER_CREATED` or `AUTHORIZED` | `webhook:payment.captured` or `webhook:order.paid` | `PAID` | VALID | Update `Order.status='PAID'`. Update/insert `Payment` as `captured`. | `transaction_finalized` |
| `ORDER_CREATED` or `AUTHORIZED` | `webhook:payment.failed` | `FAILED` | VALID | Update `Order.status='FAILED'`. Record failure code on `Payment`. | `payment_failed` |
| `PAID` | `webhook:payment.authorized` *(delayed/out-of-order)* | `PAID` | IGNORED | **No regression.** Acknowledge webhook idempotently without modifying final state. | `stale_event_ignored` |
| `PAID` | `webhook:order.paid` *(duplicate)* | `PAID` | IGNORED | Detected via `X-Razorpay-Event-Id` uniqueness. No DB changes. | `webhook_duplicate` |
| `FAILED` | `webhook:payment.captured` *(anomaly)* | `PAID` | VALID | Update state to `PAID` (capture takes precedence over earlier transient decline); flag for audit review. | `payment_state_recovered` |

---

## 3. Terminal State Invariant

Once a transaction reaches terminal state `PAID` or `FINALIZED`:
- Stale events (such as delayed `payment.authorized`) **must never regress** the order status.
- Duplicate events are trapped by the `processed_webhook_events` database uniqueness constraint.
