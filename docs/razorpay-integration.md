# Razorpay Integration Specification

This document defines the exact technical integration with Razorpay’s test-mode APIs, detailing endpoint specifications, signature verification, timeout handling, and responsibilities.

---

## 1. Scope & MVP Capabilities

The MVP integration utilizes a minimal, robust subset of Razorpay’s REST API:
1. **Order Creation**: `POST https://api.razorpay.com/v1/orders`
2. **Order Reconciliation**: `GET https://api.razorpay.com/v1/orders/{order_id}`
3. **Payment Retrieval**: `GET https://api.razorpay.com/v1/orders/{order_id}/payments`
4. **Webhook Processing**: Signed HTTP POST events (`order.paid`, `payment.captured`)

---

## 2. Authentication & Environment

- **Protocol**: HTTP Basic Authentication
  - Username: `RAZORPAY_KEY_ID` (e.g., `rzp_test_...`)
  - Password: `RAZORPAY_KEY_SECRET`
- **Environment Isolation**:
  - Test mode keys begin with prefix `rzp_test_`.
  - All test transactions use test payment instruments (e.g., test card numbers, simulated UPI handles).
  - API base URL: `https://api.razorpay.com/v1`

---

## 3. The Core Transaction Flow

```text
       ┌──────────────────────┐
       │   Validated Basket   │
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ Razorpay Test Order  │  POST /v1/orders (amount in paise, receipt = decision_id)
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ Test Checkout / Pay  │  AI Buyer completes payment using test credentials
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ Payment Captured     │  Status transitions to 'captured' / 'paid'
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ Webhook Dispatched   │  POST /api/v1/webhooks/razorpay
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ Verify & Deduplicate │  HMAC SHA256 check + X-Razorpay-Event-Id lookup
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │ Persist Outcome      │  Write to Outcome Store & feed Policy Learner
       └──────────────────────┘
```

---

## 4. Endpoint Specifications

### 4.1 Create Order (`POST /v1/orders`)
- **Headers**:
  - `Authorization`: `Basic base64(key_id:key_secret)`
  - `Content-Type`: `application/json`
- **Request Body**:
  ```json
  {
    "amount": 1600000,
    "currency": "INR",
    "receipt": "dec_9e8d7c6b5a",
    "payment_capture": 1,
    "notes": {
      "decision_id": "dec_9e8d7c6b5a",
      "merchant_id": "merch_artisanal_brew_99",
      "experiment_variant": "VARIANT_B"
    }
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "id": "order_NXK1829abcD",
    "entity": "order",
    "amount": 1600000,
    "amount_paid": 0,
    "amount_due": 1600000,
    "currency": "INR",
    "receipt": "dec_9e8d7c6b5a",
    "status": "created",
    "attempts": 0,
    "notes": { ... },
    "created_at": 1725364800
  }
  ```

### 4.2 Fetch Payments for Order (`GET /v1/orders/{order_id}/payments`)
- **Used For**: Timeout reconciliation and fallback status verification.
- **Response (200 OK)**:
  ```json
  {
    "entity": "collection",
    "count": 1,
    "items": [
      {
        "id": "pay_PLM992817x",
        "entity": "payment",
        "amount": 1600000,
        "currency": "INR",
        "status": "captured",
        "order_id": "order_NXK1829abcD",
        "method": "card",
        "captured": true,
        "error_code": null,
        "created_at": 1725364815
      }
    ]
  }
  ```

---

## 5. Webhook Ingestion & Cryptographic Verification

### 5.1 Verification Algorithm
Razorpay signs the webhook body using HMAC SHA256. The FastAPI handler must verify the signature against the **raw body buffer** before any serialization.

```python
import hmac
import hashlib

def verify_razorpay_webhook_signature(
    raw_body: bytes,
    signature_header: str,
    webhook_secret: str
) -> bool:
    expected_signature = hmac.new(
        key=webhook_secret.encode('utf-8'),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)
```

### 5.2 Deduplication via `X-Razorpay-Event-Id`
Razorpay supplies header `X-Razorpay-Event-Id` on all webhook dispatches.
```python
# Idempotency check
async def process_webhook_event(event_id: str, event_type: str, payload: dict, db: AsyncSession):
    # Attempt atomic insert into processed_webhook_events
    query = insert(ProcessedWebhookEvent).values(
        event_id=event_id,
        event_type=event_type,
        payload=payload
    ).on_conflict_do_nothing()
    
    result = await db.execute(query)
    if result.rowcount == 0:
        # Event already processed; acknowledge idempotently
        logger.info("Duplicate webhook received; skipping", event_id=event_id)
        return {"status": "already_processed"}
        
    # Process event transitions...
```

---

## 6. Order Creation Timeout & Reconciliation Protocol

> [!CAUTION]
> **Never Blindly Retry Order Creation**:
> Network timeouts during HTTP POST do not mean the order failed; Razorpay may have successfully created the order. Blindly re-posting can result in duplicate orders for the same policy decision.

### Exact Timeout Handling Flow:
```text
Application command
      ↓
internal request_id / policy_decision_id
      ↓
attempt Razorpay order creation
      ↓
[HTTP Timeout or Connection Error]
      ↓
Query internal DB for order by receipt = policy_decision_id
      ↓
If not found in local DB:
      Fetch recent orders from Razorpay API / reconcile state
      ↓
If order exists in Razorpay:
      Link razorpay_order_id to decision in DB
Else:
      Safe to retry order creation ONCE with identical receipt ID
```

---

## 7. Responsibility Division Matrix

| Responsibility | Razorpay | Application |
| :--- | :---: | :---: |
| Generating API credentials (`key_id`, `key_secret`) | ✅ | ❌ |
| Enforcing merchant margin floors & discount limits | ❌ | ✅ |
| Calculating exact basket amounts in paise | ❌ | ✅ |
| Recording transaction order immutability | ✅ | ❌ |
| Simulating card/UPI payment processing in test mode | ✅ | ❌ |
| Signing webhook payloads with HMAC SHA256 | ✅ | ❌ |
| Verifying webhook signatures with raw body bytes | ❌ | ✅ |
| Deduplicating events via `X-Razorpay-Event-Id` | ❌ | ✅ |
| Calculating observed contribution and updating policy | ❌ | ✅ |
