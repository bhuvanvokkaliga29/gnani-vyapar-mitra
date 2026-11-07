# Phase 1: Failure Modes & Timeout Reconciliation Protocol

This document details the exact reconciliation logic, timeout safeguards, and state resolution procedures for the **Merchant Policy Agent**.

---

## 1. The Core Problem: Network Uncertainty on Order Creation

When an HTTP client executes:
```text
POST https://api.razorpay.com/v1/orders
```
there are three fundamental outcome possibilities:
1. **Definitive Success**: Server processes request, returns HTTP 200 with `order_id`.
2. **Definitive Failure**: Server rejects request, returns HTTP 400 or HTTP 401 with error JSON.
3. **Indeterminate State**: Client socket times out, drops connection, or server crashes mid-flight.

> [!CAUTION]
> In an indeterminate state, the client does not know whether Razorpay created the order or not.
> **Blindly retrying `POST /orders` can create a duplicate order and double-charge a merchant or buyer.**

---

## 2. The Internal Intent & Receipt Correlation Strategy

To guarantee that an indeterminate state can be resolved without creating duplicate financial objects:

1. **Pre-Allocation**: Before making any outbound call, the application generates a unique internal `decision_id` (e.g., `dec_9a8b7c6d5e123456`).
2. **Local Persistence**: The application writes the order to the local database with `status = 'CREATION_PENDING'` and `receipt = decision_id`.
3. **Bounded Receipt**: Razorpay requires `receipt` to be $\le 40$ characters. Our decision IDs are generated with a strict length of 32 characters (e.g., `dec_` + 28 alphanumeric chars), ensuring compliance.
4. **Outbound Call**: The order creation request transmits `receipt = decision_id`.

---

## 3. The Exact Reconciliation Algorithm

When a timeout or network partition occurs during order creation:

```text
[HTTP Timeout on POST /v1/orders]
               │
               ▼
[Set local Order.status = 'UNCERTAIN']
               │
               ▼
[Audit Event: order_reconciliation_started]
               │
               ▼
[Reconciliation Query to Razorpay]
  Query recent orders or retrieve using internal receipt:
  GET /v1/orders?receipt={receipt_id} OR check payments
               │
      ┌────────┴────────┐
      ▼ [Order Found]   ▼ [Order Not Found]
[Link razorpay_order_id]    [Verify absence]
[Set status = 'ORDER_CREATED'] [Set status = 'FAILED']
[Audit: reconciliation_succeeded] [Audit: reconciliation_failed]
                            [Safe to retry with fresh intent]
```

### 3.1 Idempotent Reconciliation Service (`reconciliation.py`)
```python
async def reconcile_uncertain_order(order_id: str, db: AsyncSession, razorpay_client: RazorpayClient):
    order = await get_order(db, order_id)
    if order.status != TransactionState.UNCERTAIN:
        return order

    # Attempt to locate order via Razorpay API using receipt
    matched_order = await razorpay_client.find_order_by_receipt(order.receipt)
    if matched_order:
        order.razorpay_order_id = matched_order["id"]
        order.status = TransactionState.ORDER_CREATED
        await log_audit_event(db, "ORDER", order.id, "RECONCILIATION", "order_reconciliation_completed")
    else:
        order.status = TransactionState.FAILED
        await log_audit_event(db, "ORDER", order.id, "RECONCILIATION", "order_reconciliation_failed")

    await db.commit()
    return order
```

---

## 4. Webhook Reconciliation Fallback

If an AI buyer completes a payment but the webhook is delayed or dropped due to an external network failure:
1. When the buyer or merchant polls `GET /api/v1/orders/{id}` and finds `status == 'ORDER_CREATED'`:
2. The endpoint invokes `GET /v1/orders/{razorpay_order_id}/payments` against Razorpay.
3. If Razorpay reports a payment with `status == 'captured'`, the system reconciles the local order to `PAID`, persists the payment record, and logs an audit event (`order_reconciled_via_api`).
4. When the delayed webhook eventually arrives, it is safely recognized as a duplicate or redundant transition and acknowledged without side-effects.
