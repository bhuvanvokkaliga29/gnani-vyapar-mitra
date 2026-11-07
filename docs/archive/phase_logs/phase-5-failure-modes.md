# Phase 5 Failure Modes & Resilience Engineering

## 1. Upstream Razorpay Provider Outages
- **Scenario**: Razorpay REST API returns HTTP 5xx or connection drops during order creation.
- **Handling**:
  - Catches upstream exception.
  - Automatically releases any atomically reserved inventory (`reservation_mgr.release_inventory`).
  - Sets execution record status to `ORDER_CREATE_FAILED` and logs machine-readable code `RAZORPAY_ORDER_CREATION_FAILED`.
  - Returns safe response with zero phantom inventory loss.
- **Verified by**: `test_provider_outage_releases_inventory_safely`.

---

## 2. Network Timeout & Indeterminate State
- **Scenario**: Outbound HTTP request to Razorpay times out after order was received by Razorpay.
- **Handling**:
  - Phase 1 `OrderService` marks internal order state as `UNCERTAIN`.
  - Automatically triggers `ReconciliationService` to fetch provider truth via receipt ID.
  - Resolves internal state to `ORDER_CREATED` or `FAILED` based on provider records.
  - Prevents blind retry and duplicate charges.

---

## 3. Duplicate Client Submissions (Idempotency)
- **Scenario**: Client sends duplicate `POST /api/v1/policy/execute` requests due to network retransmits.
- **Handling**:
  - Idempotency key `(merchant_id, proposal_id, candidate_id)` is indexed in `execution_records`.
  - If existing record exists, returns existing authorization and Razorpay order reference (`is_duplicate = True`).
  - Never calls Razorpay API a second time.
  - Never reserves inventory twice.
- **Verified by**: `test_idempotent_execution_replayed_no_duplicate_order`.

---

## 4. Webhook Event Ordering & Deduplication
- **Scenario**: Razorpay sends duplicate `payment.captured` webhooks or events arrive out of sequence.
- **Handling**:
  - `ProcessedWebhookEvent` table deduplicates on `X-Razorpay-Event-Id`.
  - `StateMachine` enforces valid forward transitions and rejects terminal state regression.
  - `InventoryReservationManager.commit_inventory_deduction` permanently decrements inventory only upon verified payment.
- **Verified by**: `test_webhook_payment_captured_handoff` and Phase 1 failure suites.
