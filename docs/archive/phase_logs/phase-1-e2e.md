# Phase 1: End-to-End Test Mode Procedure

This document specifies the verification procedures for Phase 1. It explicitly distinguishes between:
1. **Automated Integration Tests (Mocked Provider)**: Fast, deterministic, isolated tests for CI and failure injection.
2. **Real Test Mode E2E (Provider-Originated Webhooks)**: Verifying actual communication with Razorpay test servers, live checkout, and provider-emitted webhooks.

---

## 1. Automated Integration Tests (Deterministic CI)

The automated test suite runs against an asynchronous SQLite test database with mocked network boundaries. It executes in $< 1$ second and validates all internal application logic.

### Execution Command:
```bash
.\.venv\Scripts\pytest.exe tests/ -v
```

### Coverage:
- **Unit (14 tests)**: Settings, money validation, HMAC cryptography, state machine.
- **Integration (6 tests)**: FastAPI endpoints, order persistence, webhook parsing.
- **Chaos Failures (7 tests)**: Invalid signature, duplicate delivery, race conditions, gateway timeouts, malformed responses, database rollback, out-of-order events.

---

## 2. Real Test Mode E2E Procedure (Live Provider Lifecycle)

This procedure verifies integration against Razorpay's actual Test Mode infrastructure (`https://api.razorpay.com/v1`).

```text
Local Application
       ↓
Create Real Razorpay Test Order (POST https://api.razorpay.com/v1/orders)
       ↓
Test Checkout (scripts/test_checkout.html with Card: 4012 0000 0000 0002)
       ↓
Razorpay processes payment and reaches "captured"
       ↓
Razorpay emits signed webhook (order.paid)
       ↓
Public HTTPS Tunnel (ngrok http 8000)
       ↓
FastAPI Ingestion (POST /webhooks/razorpay)
       ↓
Raw HMAC SHA-256 Signature Verification
       ↓
Database Deduplication & Atomic Persistence
       ↓
State Machine transitions to PAID
       ↓
Reconciliation against Razorpay API
```

---

## 3. Step-by-Step Live E2E Verification Protocol

### Step 1: Configure Real Razorpay Test Mode Credentials
In `.env`:
```ini
RAZORPAY_KEY_ID=rzp_test_your_real_key_id
RAZORPAY_KEY_SECRET=your_real_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

### Step 2: Start Local API Server
```bash
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --port 8000 --reload
```

### Step 3: Establish Public HTTPS Webhook Tunnel
To receive genuine webhooks from Razorpay cloud to your local machine:
```bash
ngrok http 8000
```
Copy the generated HTTPS URL (e.g., `https://abc1234.ngrok-free.app`).

### Step 4: Configure Webhook in Razorpay Dashboard
1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com/) in **Test Mode**.
2. Navigate to: **Settings** $\to$ **Webhooks** $\to$ **Add New Webhook**.
3. Set Webhook URL: `https://<your-ngrok-subdomain>.ngrok-free.app/webhooks/razorpay`.
4. Enter your `RAZORPAY_WEBHOOK_SECRET`.
5. Enable Active Events:
   - `order.paid`
   - `payment.captured`
   - `payment.failed`
6. Save Webhook.

### Step 5: Execute Real Test Mode Runner
```bash
.\.venv\Scripts\python.exe scripts/run_real_testmode_e2e.py
```
This runner:
1. Validates real credentials.
2. Dispatches `POST https://api.razorpay.com/v1/orders` and outputs the Razorpay Order ID.
3. Provides the browser checkout URL (`scripts/test_checkout.html?key_id=...&order_id=...`).

### Step 6: Complete Test Card Payment
1. Open the checkout link in your browser.
2. Click **Pay with Razorpay Test Mode**.
3. Enter standard Razorpay test credentials:
   - **Card Number**: `4012 0000 0000 0002`
   - **Expiry**: Any future date (e.g., `12/28`)
   - **CVV**: `123`
   - **OTP**: `123456`
4. Confirm payment.

### Step 7: Verify Provider Webhook Ingestion & State Parity
1. Observe local uvicorn logs:
   `[WEBHOOK_SERVICE] webhook_verified event_id=evt_... event_type=order.paid`
2. Verify order state via API:
   ```bash
   curl http://localhost:8000/api/v1/orders/<internal_order_id>
   ```
   Status must be `PAID`.
3. Verify reconciliation evidence recorded in `docs/evidence/phase-1-e2e-run.md`.
