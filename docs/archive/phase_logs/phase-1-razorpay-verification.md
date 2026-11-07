# Phase 1: Razorpay API & Webhook Verification

This document records the verified API capabilities, request/response requirements, signature algorithms, retryability classifications, and reconciliation mechanisms for Razorpay's Test Mode.

---

## 1. Verified API Capabilities

### 1.1 Create Order
- **Capability**: Order Creation
- **Endpoint/Event**: `POST https://api.razorpay.com/v1/orders`
- **Request Requirements**:
  - `amount`: Mandatory integer in smallest currency unit (e.g., paise for INR). No floating-point or decimals permitted (e.g., ₹100.50 must be `10050`).
  - `currency`: Mandatory 3-letter ISO code (e.g., `"INR"`).
  - `receipt`: Optional string, max 40 characters. Used for internal transaction intent tracking (`decision_id`).
  - `notes`: Optional key-value object (max 15 key-value pairs, max 256 characters per key/value).
  - `payment_capture`: Optional integer (`1` for auto-capture upon authorized payment, `0` for manual capture).
- **Response/State**:
  - HTTP 200 OK returning JSON object with `id` (e.g., `order_...`), `status` (`"created"`), `amount`, `amount_paid`, `amount_due`, `currency`, `receipt`, `created_at`.
- **Authentication**: HTTP Basic Auth with `Key ID` as username and `Key Secret` as password.
- **Test-Mode Behavior**: Creates a real order on Razorpay test servers, accessible via Razorpay Test Dashboard. Order ID is used in checkout.
- **Error Behavior**:
  - HTTP 400 Bad Request if `amount` is missing, non-integer, or negative.
  - HTTP 401 Unauthorized if API keys are invalid.
- **Source**: Razorpay Official Orders API Documentation (`razorpay.com/docs/api/orders`).
- **Verification Date**: 2026-09-03

---

### 1.2 Fetch Order by ID
- **Capability**: Retrieve Order
- **Endpoint/Event**: `GET https://api.razorpay.com/v1/orders/{order_id}`
- **Request Requirements**: `order_id` in path.
- **Response/State**:
  - HTTP 200 OK returning Order object with current `status` (`"created"`, `"attempted"`, `"paid"`), `amount_paid`, `amount_due`.
- **Authentication**: HTTP Basic Auth.
- **Test-Mode Behavior**: Returns the verified state of the test order.
- **Error Behavior**: HTTP 404 if order does not exist.
- **Source**: Razorpay Official Orders API Documentation (`razorpay.com/docs/api/orders/#fetch-an-order-with-id`).
- **Verification Date**: 2026-09-03

---

### 1.3 Fetch Payments for an Order
- **Capability**: Retrieve Order Payments (Reconciliation Anchor)
- **Endpoint/Event**: `GET https://api.razorpay.com/v1/orders/{order_id}/payments`
- **Request Requirements**: `order_id` in path.
- **Response/State**:
  - HTTP 200 OK returning collection JSON:
    `{"entity": "collection", "count": N, "items": [{ "id": "pay_...", "amount": 10000, "status": "captured", ... }]}`.
- **Authentication**: HTTP Basic Auth.
- **Test-Mode Behavior**: Returns all test payments attempted or captured against the specified order ID.
- **Error Behavior**: HTTP 404 if order does not exist; returns empty collection (`count: 0`) if no payments attempted yet.
- **Source**: Razorpay Orders API Documentation (`razorpay.com/docs/api/orders/#fetch-payments-for-an-order`).
- **Verification Date**: 2026-09-03

---

### 1.4 Webhook Signature Verification
- **Capability**: Cryptographic Payload Non-Repudiation
- **Endpoint/Event**: `X-Razorpay-Signature` header on inbound webhook POST.
- **Request Requirements**:
  - Verification requires the **exact raw request body bytes**.
  - Must NOT verify against parsed or re-serialized JSON.
  - Compute: `HMAC-SHA256(raw_bytes, secret = RAZORPAY_WEBHOOK_SECRET)`.
  - Compare computed digest against `X-Razorpay-Signature` using constant-time string comparison (`hmac.compare_digest`).
- **Response/State**:
  - If valid: Proceed with event processing.
  - If invalid: Reject immediately with HTTP 400 Bad Request.
- **Authentication**: Shared secret configured in Razorpay Dashboard.
- **Test-Mode Behavior**: Razorpay Test Mode generates signed webhooks using the configured test webhook secret.
- **Error Behavior**: Mismatched signature indicates payload tampering or incorrect secret.
- **Source**: Razorpay Webhooks Signature Verification (`razorpay.com/docs/webhooks/validate-test`).
- **Verification Date**: 2026-09-03

---

### 1.5 Webhook Event Deduplication (`X-Razorpay-Event-Id`)
- **Capability**: Inbound Event Idempotency
- **Endpoint/Event**: `X-Razorpay-Event-Id` header on inbound webhook POST.
- **Request Requirements**: Extract header string value (e.g., `evt_...`).
- **Response/State**:
  - Atomic database insertion into `processed_webhook_events`.
  - If event ID already exists in database: Return HTTP 200 OK immediately without re-executing state transitions.
- **Test-Mode Behavior**: Test mode dispatches `X-Razorpay-Event-Id` on all webhook payloads.
- **Error Behavior**: Network retries from Razorpay will carry the identical `X-Razorpay-Event-Id`.
- **Source**: Razorpay Webhooks Best Practices (`razorpay.com/docs/webhooks/best-practices`).
- **Verification Date**: 2026-09-03

---

### 1.6 Key Webhook Events
- **`order.paid`**: Dispatched when an order has been successfully paid in full. Payload contains `order` and `payment` entities.
- **`payment.captured`**: Dispatched when a payment transitions from `authorized` to `captured`.
- **`payment.failed`**: Dispatched when a test or live payment attempt fails or is declined.
- **Source**: Razorpay Webhook Event Types Reference.
- **Verification Date**: 2026-09-03

---

## 2. API Call Retryability Classification

To ensure financial safety, all provider interactions are strictly classified into three behavioral categories:

| API Operation | HTTP Method & Path | Classification | Recovery / Retry Protocol |
| :--- | :--- | :--- | :--- |
| **Order Creation** | `POST /v1/orders` | **MUST NEVER BE BLINDLY RETRIED** | On timeout, mark local state `UNCERTAIN`. Query Razorpay by `receipt` ID. If order exists, associate it; if confirmed absent, safe to retry once. |
| **Payment Capture** | `POST /v1/payments/{id}/capture` | **MUST NEVER BE BLINDLY RETRIED** | On timeout, fetch payment status via `GET /v1/payments/{id}`. Only retry if status is confirmed `authorized`. |
| **Order Status Retrieval** | `GET /v1/orders/{order_id}` | **SAFE TO RETRY** | Pure idempotent read operation. Safe to retry with exponential backoff on network failures. |
| **Order Payments Retrieval**| `GET /v1/orders/{order_id}/payments` | **SAFE TO RETRY** | Pure idempotent read operation. Primary mechanism for reconciling payment state if webhooks are delayed. |
| **Payment Status Retrieval**| `GET /v1/payments/{payment_id}` | **SAFE TO RETRY** | Pure idempotent read operation. |
| **Webhook Processing** | `POST /webhooks/razorpay` | **IDEMPOTENT VIA EVENT ID** | Inbound endpoint enforces database-level uniqueness on `X-Razorpay-Event-Id`. Duplicate deliveries return 200 OK without side effects. |
