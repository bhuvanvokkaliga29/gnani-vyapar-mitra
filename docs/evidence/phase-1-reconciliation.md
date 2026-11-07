# Phase 1: Provider Reconciliation Evidence

This document outlines the operational verification of the reconciliation subsystem between local PostgreSQL state and Razorpay Test Mode API state.

---

## 1. Reconciliation Architecture

```text
Local Transaction State
        ↕ (Reconciliation Anchor)
Razorpay Orders & Payments APIs
```

Reconciliation operates across two specific operational scenarios:
1. **Creation Timeout Reconciliation**: Resolves indeterminate order status when `POST /v1/orders` times out on the network.
2. **Payment Webhook Gap Reconciliation**: Resolves orders when incoming webhook events are delayed, lost, or need active synchronization against Razorpay's Payments API (`GET /v1/orders/{order_id}/payments`).

---

## 2. Order Creation Timeout Verification

### Fault Injected:
- A network drop/timeout is triggered after Razorpay's gateway registers an order, but before returning HTTP 200 to the client application.

### State Transition & Execution Log:
```text
[ORDER_SERVICE] Pre-allocating Order: ord_test_rec_1, Status: CREATION_PENDING, Receipt: dec_test_rec_1
[RAZORPAY_CLIENT] POST /v1/orders -> RazorpayTimeoutError ("Gateway connection timed out")
[ORDER_SERVICE] Catching timeout -> Setting Order status to UNCERTAIN
[RECONCILIATION] Triggering immediate reconciliation for Order: ord_test_rec_1 (Receipt: dec_test_rec_1)
[RAZORPAY_CLIENT] GET /v1/orders?count=50
[RECONCILIATION] Match found! Razorpay Order ID: order_timeout_created matches Receipt: dec_test_rec_1
[ORDER_SERVICE] Updating Order ord_test_rec_1 -> razorpay_order_id = order_timeout_created
[STATE_MACHINE] Validating transition: UNCERTAIN -> ORDER_CREATED (VALID)
[AUDIT] Action: order_reconciliation_completed, Actor: RECONCILIATION_SERVICE, Entity: ORDER ord_test_rec_1
```

### Invariant Verified:
- **Zero Duplicate Financial Orders**: The application never dispatched a second `POST /v1/orders`. State was cleanly recovered from the gateway. Verified by `tests/integration/test_failures.py::test_failure_4_order_creation_timeout_reconciliation`.

---

## 3. Order Payment State Verification (`GET /v1/orders/{order_id}/payments`)

When reconciling an existing order:
1. `ReconciliationService.reconcile_order()` executes `GET /v1/orders/{order_id}/payments`.
2. Evaluates returned items:
   - Matches `order_id` and checks if any payment has `status == "captured"`.
   - Compares total `amount` against local order `amount_paise`.
3. If payment is captured:
   - Updates `Order.status = "PAID"`.
   - Inserts or updates corresponding `Payment` entity with `status = "captured"`.
   - Logs `reconciliation_completed` in `audit_events`.

---

## 4. Local vs. Provider State Parity

| Metric | Local Database State | Razorpay Gateway State | Parity Status |
| :--- | :--- | :--- | :---: |
| **Order Status** | `PAID` | `paid` | **MATCH** |
| **Amount (paise)** | `150000` | `150000` | **MATCH** |
| **Currency** | `INR` | `INR` | **MATCH** |
| **Receipt Tracking** | `dec_...` | `dec_...` | **MATCH** |
| **Payment Status** | `captured` | `captured` | **MATCH** |
