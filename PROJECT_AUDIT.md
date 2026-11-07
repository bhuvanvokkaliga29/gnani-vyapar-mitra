# 📋 Vyapar Mitra — Comprehensive Project Audit
**Competition**: The Great Indian AI Internship Challenge 2026 (Gnani AI)  
**Team**: Bhuvan Gowda H K & Dhanush A G  
**Date**: November 2026  
**Repository Working Directory**: `c:\Users\HP\Downloads\merchant-policy-agent`  
**Audit Author**: Senior AI Engineer & Full-Stack Architect  

---

## 1. Executive Summary

This audit assesses the local clone of the **Vyapar Mitra** codebase (repository lineage: `merchant-policy-agent`). The project was originally engineered as an autonomous commercial policy engine and transaction substrate for the Razorpay AI Buildathon 2026. It possesses a highly sophisticated, mathematically rigorous core:
- A contextual multi-armed bandit (**LinUCB**) for learning optimal merchant pricing and bundling policies.
- An 11-stage decision pipeline enforcing deterministic gross margin floors ($\ge 25\%$) and discount ceilings ($\le 20\%$).
- Cryptographically verified Razorpay test-mode payment capture and idempotent webhook reconciliation.
- An immutable append-only database audit ledger (`AuditEvent`).
- A Next.js 16 merchant dashboard with an Instagram-style 4-tab mobile-first navigation bar.
- WhatsApp Business integration via Meta Cloud API and a local `whatsapp-web.js` QR-connector.

### The Opportunity for Gnani AI Challenge 2026
While the autonomous transaction substrate is production-grade, the conversational AI, regional voice interaction, and Doctor consulting layer are either nascent, simulated, or missing:
1. **Zero Gnani AI Integration**: There are currently **no** calls to Gnani Prisma (STT) or Gnani Timbre (TTS). Voice in WhatsApp currently relies on Microsoft `edge-tts` falling back to Google `gTTS`. Voice transcription in the AI Studio uses standard browser `webkitSpeechRecognition` with static simulated fallbacks.
2. **Growth Doctor UI Disconnect**: The 3rd bottom navigation tab (`/doctor`) displays static and semi-static diagnostic cards (dead stock, margin leakage, price gaps) rather than an interactive AI Business Voice Advisor. There is no microphone recorder, circular audio visualizer, or spoken response player on this screen.
3. **Hardcoded Frontend Projections**: The Overview page (`apps/web/src/app/page.tsx`) contains a client-side mock search regex (`handleAskAgent`) that returns static strings for sales, inventory, and profit queries instead of querying the backend.
4. **Catalogue & Data Gaps**: The apparel catalog currently contains only 8 baseline SKUs, and historical orders are sparsely seeded. A realistic 50–100 SKU fashion-retail catalog with consistent 30-day orders and channel attribution is needed.
5. **Brand Transition Artifacts**: While the UI branding has been updated to **Vyapar Mitra** and the demo merchant to **Vastram**, internal identifiers (`merch_atlas_travel`), default product hints (`Atlas Apex Pro Backpack`), and WhatsApp greetings still reference the legacy Atlas Travel Gear demo.

---

## 2. Technology Stack & Framework Inventory

| Layer | Technologies & Frameworks | Version / Specification | Location |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | Next.js (App Router), React, TypeScript | Next.js 16.3.4, React 19.2.8, TS 5.0 | `apps/web/` |
| **Styling & Icons** | Tailwind CSS, Lucide React, Recharts | Tailwind CSS v4, Lucide 1.40.0, Recharts 3.10 | `apps/web/src/` |
| **Backend API Gateway** | FastAPI, Uvicorn (standard async) | FastAPI 0.111+, Uvicorn 0.30+ | `apps/api/` |
| **Data & ORM Layer** | SQLAlchemy (asyncio), AsyncPG, AioSQLite, Alembic | SQLAlchemy 2.0.30+, Alembic 1.13+ | `domain/models.py`, `apps/api/core/database.py` |
| **AI Reasoning Engine** | Google Gemini REST API Client (`httpx`) | Gemini 1.5 Flash via REST (`v1beta`) | `services/policy/llm_client.py` |
| **Speech-to-Text (STT)** | Browser Web Speech API (Simulated Fallback) | *Gnani Prisma NOT YET INTEGRATED* | `apps/web/src/components/products/AIProductStudioModal.tsx` |
| **Text-to-Speech (TTS)** | Edge-TTS & gTTS (WhatsApp Voice Notes) | *Gnani Timbre NOT YET INTEGRATED* | `services/whatsapp/media_generator.py` |
| **Messaging & Channels** | Meta WhatsApp Cloud API + `whatsapp-web.js` | Meta Graph API v21.0, Node.js Connector | `services/whatsapp/`, `connector/` |
| **Payments & Settlement** | Razorpay Test Mode API & Webhooks | Official Razorpay Orders & HMAC Webhook | `services/razorpay/` |
| **Protocol Extensions** | Model Context Protocol (MCP 2026) | FastMCP JSON-RPC 2.0 / SSE / Stdio | `services/mcp/` |
| **Document Generation** | ReportLab | ReportLab 4.0+ (PDF Sales Statements) | `services/whatsapp/media_generator.py` |

---

## 3. Directory Structure & Code Organization

```
merchant-policy-agent/
├── apps/
│   ├── api/                     # FastAPI Backend Application
│   │   ├── core/                # Config, DB async engine, Auth, Middleware, State Machine
│   │   ├── routers/             # 25+ REST routers (dashboard, doctor, whatsapp, orders, etc.)
│   │   └── main.py              # Application entrypoint & lifespan management
│   └── web/                     # Next.js 16 Frontend Web Application
│       ├── src/
│       │   ├── app/             # App Router pages: /, /doctor, /products, /whatsapp, etc.
│       │   ├── components/      # UI components (AppShell, modals, drawers)
│       │   └── lib/             # API client (api.ts), MerchantContext.tsx, types.ts
│       └── package.json
├── connector/                   # Local Node.js WhatsApp Web Connector (whatsapp-web.js)
├── domain/                      # SQLAlchemy models & Pydantic commerce schemas
│   ├── models.py                # 26 core tables (Merchants, Products, Orders, LinUCB, Audits)
│   ├── growth_models.py         # Growth Doctor findings, channel configs, approval items
│   ├── whatsapp_models.py       # Webhook logs, pending confirmations, outbound logs
│   ├── commerce_schemas.py      # Typed DTOs for products, merchants, constraints
│   └── intent_schemas.py        # Buyer intent representations
├── services/                    # Domain logic & business services
│   ├── agent/                   # Agent abstractions
│   ├── audit/                   # Append-only immutable audit trail service
│   ├── benchmark/               # Benchmark scenario runners & observers
│   ├── commerce/                # Product catalog & inventory management
│   ├── dashboard/               # Read projections for Next.js dashboard
│   ├── growth_doctor/           # Deterministic diagnostic analysis service
│   ├── learning/                # LinUCB bandit update & model persistence
│   ├── marketplace/             # Amazon, Flipkart, Meesho net contribution models
│   ├── policy/                  # Gemini LLM client, prompts, safety validator, ranker
│   ├── razorpay/                # Razorpay orders, payments, webhooks, reconciliation
│   └── whatsapp/                # Meta Cloud API, intent parser, confirmation manager
├── scripts/                     # Seed scripts, DB audits, E2E demo runners
├── tests/                       # 960+ unit, integration, and E2E test suites
└── submission/                  # Hackathon documentation, screenshots, benchmark outputs
```

---

## 4. Current State of Database & Data Consistency

1. **Active Database Engine**: Default configuration in `apps/api/core/config.py` points to `sqlite+aiosqlite:///./test.db`, with production override for PostgreSQL via `DATABASE_URL`.
2. **Current Seed Data**:
   - `scripts/seed_commerce_data.py`: Seeds `merch_atlas_travel` with 4 travel backpack SKUs.
   - `scripts/update_vastram_clothing.py`: Renames `merch_atlas_travel` to "Vastram", clears old backpack products, and inserts 8 clothing SKUs (3 shirts, 3 trousers, 2 accessories).
   - `scripts/seed_vastram_orders.py`: Inserts ~35 mock orders for Vastram for October 17, 2026.
3. **Data Gaps**:
   - The catalog currently has only 8 active apparel products in SQLite.
   - The frontend `apps/web/src/app/page.tsx` hardcodes today's revenue to ₹44,982 across 18 orders in simulated local arrays instead of binding directly to database aggregations.
   - `apps/web/src/app/doctor/page.tsx` hardcodes an `OCTOBER_DAILY_SALES` array (Oct 1–18) inside the component rather than fetching dynamic rolling sales from the backend.
   - Growth Doctor diagnostic findings are partly hardcoded in `VASTRAM_APPAREL_FINDINGS` inside the frontend component as a fallback.

---

## 5. Security & Sensitive Data Audit

1. **Environment Variables**:
   - `.env.example` is present and contains placeholder values (`rzp_test_...`, `your_llm_api_key_here`).
   - Secrets are masked during logging via `Settings.sanitized_dict()` in `apps/api/core/config.py`.
   - No hardcoded secrets were detected in git commits or public source files.
2. **Financial Boundaries**:
   - The codebase strictly enforces integer minor units (`paise`) across all models, preventing floating-point rounding errors.
   - Core invariant preserved: *The LLM can propose, but cannot execute financial transactions or spend capital.* Execution requires deterministic validation gates.
3. **Tenant Isolation**:
   - APIs enforce `X-Caller-Merchant-ID` verification via `verify_merchant_authorization` in `apps/api/core/auth.py`.

---

## 6. Audit Verdict & Immediate Priorities

| Dimension | Current Grade | Status | Action Required |
| :--- | :--- | :--- | :--- |
| **Transaction Core** | **A+** | Production Grade | Preserve completely; do not touch working LinUCB or Razorpay gates. |
| **Frontend UI/UX** | **A** | Premium Design | Preserve visual identity; convert Doctor page into AI voice advisor. |
| **Gnani AI Integration** | **F** | Not Started (0%) | **Urgent**: Integrate Gnani Prisma STT & Gnani Timbre TTS in backend & frontend. |
| **Gemini Integration** | **B+** | Partial | Existing in policy candidate ranking; expand into Doctor reasoning agent. |
| **Business Data Scale** | **C** | Limited (8 SKUs) | Expand to 50–100 realistic apparel SKUs with consistent 30-day orders. |
| **Doctor Experience** | **C-** | Static Cards | Transform `/doctor` into the flagship Voice Advisor with visualizer & traces. |
| **Callback Workflow** | **D** | Not Implemented | Create callback request model, API router, and interactive UI workflow. |

