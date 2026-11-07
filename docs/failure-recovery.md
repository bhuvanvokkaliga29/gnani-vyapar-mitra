# Failure Modes, Detection & Graceful Recovery

This document details the comprehensive failure matrix, automated detection mechanisms, deterministic recovery procedures, and audit requirements across all operational failure scenarios.

---

## 1. Failure Handling Philosophy: Fail Safe, Fail Visible

When an autonomous system operates on commerce and transactions, pretending success or guessing in the face of ambiguity causes catastrophic financial damage.
The system enforces three immutable recovery rules:
1. **Never guess**: If validation fails or data is missing, reject or fallback to safe baseline.
2. **Never duplicate financial mutations**: If a network request times out, reconcile state before retrying.
3. **Always record an audit trace**: Every failure must write an immutable audit log entry for human inspection.

---

## 2. Comprehensive Failure Recovery Matrix

| Failure Mode | Detection Mechanism | Automated Recovery Procedure | Merchant-Visible State | Audit Record Fields |
| :--- | :--- | :--- | :--- | :--- |
| **Malformed LLM Output** | Pydantic `ValidationError` upon parsing LLM JSON response. | Reject candidate proposal immediately. Fall back to merchant's default static catalog offer (CONTROL). | "Fallback Applied: AI Proposal unparsable" | `error_type: PARSE_ERROR`, `raw_llm_output`, `fallback_strategy_id` |
| **LLM Service Downtime / Timeout** | `httpx.TimeoutException` or HTTP 5xx from model endpoint. | Bypass strategy generator. Execute deterministic fallback rule using static catalog baseline. | "LLM Degraded: Serving static baseline" | `error_type: MODEL_UNAVAILABLE`, `endpoint_latency_ms`, `fallback_applied: TRUE` |
| **Policy Violates Margin Floor** | Deterministic Engine check: `Gross Margin % < Margin Floor %`. | Immediate rejection of proposal. Strategy is marked REJECTED; fallback to non-discounted single product. | "Candidate Rejected: Margin floor breach" | `error_type: MARGIN_VIOLATION`, `proposed_margin_pct`, `floor_pct` |
| **Discount Exceeds Merchant Limit** | Deterministic Engine check: `Discount % > Discount Ceiling %`. | Immediate rejection. Fall back to standard catalog pricing. | "Candidate Rejected: Discount ceiling exceeded" | `error_type: DISCOUNT_EXCEEDED`, `proposed_discount_pct`, `ceiling_pct` |
| **Basket Exceeds Buyer Budget** | Deterministic Engine check: `Total Basket > Buyer Budget`. | Reject proposal. If single product fits budget, offer single product; otherwise return graceful "budget mismatch" response. | "Candidate Rejected: Exceeds buyer budget" | `error_type: BUDGET_EXCEEDED`, `proposed_total_paise`, `buyer_budget_paise` |
| **Product Out of Stock** | Database inventory check: `inventory_count < requested_qty`. | Reject candidate bundle. Trigger candidate re-generation excluding out-of-stock SKU or serve available core item. | "Candidate Adjusted: SKU out of stock" | `error_type: OUT_OF_STOCK`, `sku`, `requested_qty`, `available_qty` |
| **Razorpay Order Creation Timeout** | `httpx.TimeoutException` or HTTP 504 on `POST /v1/orders`. | **DO NOT blindly retry POST.** Query local DB by `receipt = decision_id`. Reconcile against Razorpay API. If order exists, resume; if verified absent, retry once. | "Order Pending: Reconciling gateway state" | `error_type: GATEWAY_TIMEOUT`, `receipt_id`, `reconciliation_attempted: TRUE` |
| **Duplicate Webhook Delivery** | Database duplicate key violation on `X-Razorpay-Event-Id` in `processed_webhook_events`. | Acknowledge with HTTP 200 immediately without executing state transitions or duplicate policy updates. | "Webhook Deduplicated: Event already recorded" | `error_type: DUPLICATE_WEBHOOK`, `event_id`, `first_processed_at` |
| **Out-of-Order Webhook Delivery** | `order.paid` arrives before local order state updated, or `payment.captured` arrives first. | Lookup order by `razorpay_order_id`. Update payment and transition order directly to `PAID`. | "Order Paid: Asynchronous reconciliation" | `event_type`, `current_status: PAID`, `out_of_order: TRUE` |
| **Database Failure / Aborted Transaction** | SQLAlchemy `DBAPIError` or connection timeout during state commit. | Abort transaction with rollback. Do not confirm success to external client. Return HTTP 503. | "System Temporarily Unavailable" | `error_type: DATABASE_ERROR`, `sql_state`, `rolled_back: TRUE` |

---

## 3. Detailed Gateway Timeout Reconciliation Logic

```python
async def create_razorpay_order_safely(
    client: RazorpayClient,
    decision_id: str,
    amount_paise: int,
    db: AsyncSession
) -> RazorpayOrder:
    # 1. Check if order record already created locally
    existing_order = await get_order_by_receipt(db, receipt=decision_id)
    if existing_order and existing_order.razorpay_order_id:
        return existing_order

    try:
        # 2. Attempt creation with timeout
        response = await client.create_order(
            amount=amount_paise,
            currency="INR",
            receipt=decision_id
        )
        return await record_order_success(db, decision_id, response["id"])

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.warn("Gateway timeout creating order; reconciling state", decision_id=decision_id)
        
        # 3. Reconcile: Query Razorpay to see if order was actually received
        reconciled_order = await client.find_order_by_receipt(receipt=decision_id)
        if reconciled_order:
            logger.info("Order discovered via reconciliation", razorpay_id=reconciled_order["id"])
            return await record_order_success(db, decision_id, reconciled_order["id"])
            
        # 4. If confirmed absent after verification, retry once
        logger.info("Order verified absent; retrying creation once", decision_id=decision_id)
        retry_response = await client.create_order(
            amount=amount_paise,
            currency="INR",
            receipt=decision_id
        )
        return await record_order_success(db, decision_id, retry_response["id"])
```
