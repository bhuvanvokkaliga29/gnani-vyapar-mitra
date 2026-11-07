# 📊 Vyapar Mitra — Feature Implementation Status Matrix
**Competition**: The Great Indian AI Internship Challenge 2026 (Gnani AI)  
**Document**: Feature Status & Incomplete Functionality Audit  
**Status Date**: November 2026  

---

## 1. Feature Implementation Matrix

| Subsystem / Feature | Implementation Location | Current Status | Notes & Verification Findings |
| :--- | :--- | :--- | :--- |
| **LinUCB Contextual Bandit** | `services/learning/` | 🟢 **100% Operational** | Fully operational; online covariance updates, 19-dim feature vectors, anti-temporal leakage checks. Verified by 150+ unit tests. |
| **Razorpay Test Integration** | `services/razorpay/` | 🟢 **100% Operational** | Order creation, payment capture, webhook HMAC verification, and reconciliation working. |
| **Immutable Audit Log** | `services/audit/` | 🟢 **100% Operational** | Append-only `audit_events` table blocking UPDATE and DELETE statements. |
| **Multi-Tenant Authorization** | `apps/api/core/auth.py` | 🟢 **100% Operational** | Enforces `X-Caller-Merchant-ID` header tenant isolation. |
| **WhatsApp Connector (Local)** | `connector/index.js` | 🟢 **100% Operational** | `whatsapp-web.js` running with terminal QR authentication and media delivery. |
| **Overview Dashboard UI** | `apps/web/src/app/page.tsx` | 🟡 **Partially Working** | UI layout is visually rich and polished, but the Ask Agent input (`handleAskAgent`, L83-98) uses hardcoded regex replies, and today's orders list (L134) uses a static in-memory array. |
| **Growth Doctor Tab UI** | `apps/web/src/app/doctor/page.tsx` | 🟡 **Partially Working** | Currently renders static diagnostic cards (`VASTRAM_APPAREL_FINDINGS`) and a hardcoded Oct 1–18 daily sales chart. **Lacks interactive voice assistant, microphone input, and audio playback.** |
| **Product Studio** | `apps/web/src/app/studio/` | 🟡 **Partially Working** | Image preview works. Audio memo uses browser `webkitSpeechRecognition` with simulated fallback text. Still references Atlas backpacks by default in `merchants.py` (L136-193). |
| **Catalog Baseline Data** | `apps/web/src/app/products/` | 🟡 **Partially Working** | Only 8 clothing SKUs defined in `BASELINE_APPAREL`. Needs realistic expansion to 50–100 fashion/retail SKUs. |
| **Marketplace Margin Sim** | `services/marketplace/` | 🟡 **Partially Working** | Mathematical formulas for Amazon, Flipkart, Meesho fee deductions implemented, but channel comparisons are not yet surfaced in the Doctor conversation. |
| **Gemini LLM Integration** | `services/policy/llm_client.py` | 🟡 **Partially Working** | Functional for generating policy strategy candidates in the transaction pipeline. Not yet connected to an interactive Doctor conversational reasoning agent. |
| **Gnani Prisma (STT)** | *Missing* | 🔴 **0% Implemented** | No backend client, no audio upload endpoint, no language model mapping for Kannada, Hindi, or code-mixed speech. |
| **Gnani Timbre (TTS)** | *Missing* | 🔴 **0% Implemented** | No backend client, no voice synthesis router, no audio streaming to frontend. WhatsApp uses `edge-tts`/`gTTS`. |
| **Doctor Circular Voice UI** | *Missing* | 🔴 **0% Implemented** | No animated circular voice visualizer, no listening/processing/responding state machine in the UI. |
| **Voice Doctor Backend Tools** | *Missing* | 🔴 **0% Implemented** | No structured tool registry connecting merchant voice questions ("How much did I sell today?") to live SQL calculations. |
| **Request a Callback Workflow** | *Missing* | 🔴 **0% Implemented** | No database model or UI drawer for merchants to request outbound voice consultation. |
| **Merchant Action Approval** | `services/owner_policy/` | 🟡 **Partial Backend** | `OwnerApprovalItem` exists in database schema, but Doctor UI lacks one-click approval/rejection lifecycle cards for voice-recommended actions. |

---

## 2. Hardcoded & Simulated Code Regions (Must Be Replaced)

### A. Overview Page Ask Agent (`apps/web/src/app/page.tsx`, Lines 83–98)
```typescript
// CURRENT CODE: Client-side regex returning static hardcoded strings
if (qLower.includes('sales') || qLower.includes('order') || qLower.includes('revenue')) {
  ans = `📊 Sales Summary Today: You have recorded 18 paid orders totaling ₹44,982 across WhatsApp Direct and Amazon India...`;
} else if (qLower.includes('stock') || qLower.includes('reorder')) {
  ans = `⚠️ Stock Alert: Vastram Classic Jet Black Formal Trousers have only 6 units remaining...`;
}
```
**Fix Required**: Point to `api.queryDoctorAgent({ query, merchant_id })` to execute deterministic backend analytics and Gemini interpretation.

### B. Doctor Page Diagnostic Findings (`apps/web/src/app/doctor/page.tsx`, Lines 31–182)
`VASTRAM_APPAREL_FINDINGS` is hardcoded directly inside the frontend page as a static array. If the backend fails or returns empty data, the user sees identical static numbers.  
**Fix Required**: Compute findings dynamically via `GrowthDoctorService.analyze_merchant()` against the expanded 50–100 SKU database.

### C. Daily Sales Chart (`apps/web/src/app/doctor/page.tsx`, Lines 184–204)
`OCTOBER_DAILY_SALES` is hardcoded as an 18-day static array ending on Oct 18.  
**Fix Required**: Provide an API endpoint `/api/v1/doctor/daily-sales` that aggregates real order history from `orders` and `payments` tables.

### D. Default Product Studio AI Refinement (`apps/api/routers/merchants.py`, Lines 136–193)
Defaults unknown product uploads to "Travel Backpack" and "Atlas Apex Pro Backpack".  
**Fix Required**: Update prompt heuristics to default to apparel (e.g., Casual Shirt, Formal Trousers, Kurti, T-Shirt) or generic retail categories.

---

## 3. Legacy Brand Artifacts Requiring Cleanup

| File | Legacy String | Required Replacement |
| :--- | :--- | :--- |
| `apps/api/core/config.py` | `WHATSAPP_DEFAULT_MERCHANT_ID = "merch_atlas_travel"` | Retain tenant ID for backwards compatibility, but map display name strictly to **Vastram**. |
| `apps/web/src/app/whatsapp/page.tsx` (L47) | `"Welcome to the Atlas Travel Gear AI WhatsApp Business Assistant"` | `"Welcome to Vyapar Mitra — Vastram Business Advisor"` |
| `connector/index.js` (L43) | `"Vastram Merchant Growth Agent — WhatsApp Web Connector"` | Align branding with **Vyapar Mitra (Har Dukaan Ka Apna Mitra)** |
| `scripts/seed_commerce_data.py` | Seeds backpack products | Replaced by comprehensive Vastram apparel seed script |

