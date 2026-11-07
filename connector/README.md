# WhatsApp Web Local Connector — Merchant Growth Agent

This connector provides a direct, zero-cost conversational interface for the **Vastram Merchant Growth Agent** using `whatsapp-web.js`.

It connects to WhatsApp Web via a headless Chromium session, displays a scannable QR code in your terminal, and forwards messages between your mobile phone and the FastAPI backend.

---

## Architecture

```
[Merchant Mobile WhatsApp]  (+919113960498)
           │
           │ WhatsApp Messages
           ▼
[Agent WhatsApp Account / WhatsApp Web]
           │
           │ whatsapp-web.js (LocalAuth session)
           ▼
[connector/index.js]
           │
           │ POST /api/v1/whatsapp/connector-inbound
           ▼
[FastAPI Backend :8000]
  ├── Intent Parser (English, Kannada, Hindi)
  ├── Policy Guardrails (Margin Floor enforcement)
  ├── 15-Minute Single-Use Confirmation Tokens
  └── Database (Orders, Products, Audit Ledger)
           │
           │ Returns JSON { reply, intent }
           ▼
[connector/index.js]
           │
           │ msg.reply(replyText)
           ▼
[Merchant Mobile WhatsApp]
```

---

## Quick Setup & Launch

### Step 1: Install Dependencies
Open a terminal in the `connector/` directory:
```bash
cd connector
npm install
```

### Step 2: Ensure FastAPI Backend is Running
In the root directory, ensure the backend dev server is active:
```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Launch Connector
In the `connector/` directory:
```bash
node index.js
```

### Step 4: Scan the QR Code
1. A QR code will render in your terminal.
2. Open WhatsApp on the phone number you want to act as the **Agent** (or a second WhatsApp account).
3. Go to **Settings** > **Linked Devices** > **Link a Device**.
4. Scan the terminal QR code.
5. The terminal will log:
   ```
   🔐 Authentication successful! Session persisted in ./.wwebjs_auth
   ✅ WhatsApp Web Client is ONLINE and READY!
   ```
   *(Subsequent launches will re-use the stored session without re-scanning).*

---

## Demo Test Commands (From Your Phone: `+919113960498`)

Send any of the following 6 supported commands from your personal WhatsApp to the Agent number:

1. **Today's Sales & Revenue Report**:
   ```
   Show today's sales
   ```
   *Alternative: `Download the previous week sales report`*
   *Retrieves actual realized revenue (₹48,081), prepaid Razorpay vs COD order split, top-selling items, and order ledger URL.*

2. **Catalog Overview**:
   ```
   Show my products
   ```
   *Retrieves all active items directly from the database with real retail price, unit cost (COGS), gross margin %, and live stock counts.*

3. **Margin Economics & Policy Floor Inspection**:
   ```
   Which products have low margins?
   ```
   *Ranks catalog products by gross margin against the store's configured 18.0% margin floor and suggests margin-preserving price adjustments.*

4. **AI Offer Recommendation**:
   ```
   Suggest an offer for Product A
   ```
   *Recommends a policy-compliant promotional discount (10% OFF at ₹1,889) that protects the 18% margin floor.*

5. **Stock Adjustment (Guarded by Confirmation PIN)**:
   ```
   Update Product A stock to 25
   ```
   *Generates a single-use 4-digit confirmation PIN (valid 15 minutes).*
   *Reply: `CONFIRM <PIN>` or `YES` to commit the stock update to the database and record an audit log.*

6. **Price Change & Policy Guardrail**:
   ```
   Change Product A price to 499
   ```
   *Deterministic policy engine intercepts the violation (cost is ₹920; ₹499 would yield -84.4% margin).*
   *Calculates the safe compliant price (₹1,122) and asks for confirmation.*
   *Reply: `CONFIRM <PIN>` or `YES` to accept.*

---

## Security, Loop Prevention & Reliability

- **Infinite Reply Loop Prevention**: Explicitly discards `msg.fromMe == true` to prevent the connector from replying to itself.
- **Noise & Group Filtering**: Ignores WhatsApp status/stories (`status@broadcast`) and group chats (`@g.us`).
- **Request Deduplication**: In-memory LRU cache of 500 message IDs plus database message ID uniqueness in `WhatsAppWebhookLog`.
- **Session Privacy**: Stored in `./.wwebjs_auth/` (configured in `.gitignore` to prevent credential leaks).
- **Audit Logging**: Every confirmed price or inventory change writes an immutable `AuditEvent` with actor `WHATSAPP_OPERATOR`.

---

## ⚠️ Important Limitations & Unofficial Integration Risks

> [!WARNING]
> **Unofficial Protocol Risk**: `whatsapp-web.js` automates WhatsApp Web via Puppeteer. WhatsApp may detect automated patterns and restrict or temporarily ban accounts using unofficial web automation.
>
> **Separate Account Requirement**: The Agent WhatsApp account must be a distinct phone number/account that you own or are authorized to use. The connector **does not** generate or provision a phone number.
>
> **Session Invalidation**: WhatsApp Web sessions can be logged out from the mobile app's "Linked Devices" screen or invalidated by WhatsApp updates. If this happens, delete `connector/.wwebjs_auth` and scan the QR code again.
>
> **Fallback Alternative**: If WhatsApp Web automation is restricted or unsuitable in production, use the built-in Twilio WhatsApp adapter (`services/whatsapp/twilio_adapter.py`) or Meta Cloud API webhook (`/api/v1/whatsapp/webhook`).
