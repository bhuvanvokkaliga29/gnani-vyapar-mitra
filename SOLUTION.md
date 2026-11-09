# Vyapar Mitra — Har Dukaan Ka Apna Mitra
### Solution Pitch & Architecture Overview

**Team Cortex:** Bhuvan Gowda H K & Dhanush A G  
**Live Application:** [https://gnani-vyapar-mitra-apps.vercel.app/](https://gnani-vyapar-mitra-apps.vercel.app/)  
**GitHub Repository:** [https://github.com/bhuvanvokkaliga29/gnani-vyapar-mitra](https://github.com/bhuvanvokkaliga29/gnani-vyapar-mitra)

---

### 1. The Problem Faced by Small Merchants

Millions of independent retail merchants and neighborhood shopkeepers across India power local commerce, yet face severe operational disadvantages:

- **Language & Technology Barriers:** Existing retail ERP and analytics dashboards are desktop-oriented, complex, and English-centric, requiring manual data entry and accounting expertise.
- **Unmonitored Inventory & Margin Leakage:** Merchants lack in-house analysts to compute inventory holding costs, track dead stock, or anticipate reorder thresholds, resulting in locked capital or missed sales.
- **Marketplace Commission Drain:** Online aggregators charge high take-rates and return penalties, yet merchants lack clear visibility into unit economics across direct WhatsApp and marketplace channels.

---

### 2. Our Proposed AI-Powered Solution

**Vyapar Mitra ("Every Shop's Companion")** is an autonomous, conversational voice and commerce intelligence agent built specifically for Indian retail merchants. Instead of navigating complicated dashboards, shop owners can simply **speak in their native language** (Kannada, Hindi, English, or code-mixed Kanglish) to receive real-time sales diagnoses, stock reorder guidance, and commercial recommendations backed by deterministic database facts.

---

### 3. Key Capabilities

- **Conversational Voice Assistant:** Real-time spoken dialogue with automatic language detection, turn-taking, interruption handling, and natural pronunciation of Indian numbering (rupees, thousands, lakhs).
- **Deterministic Sales & Profit Analytics:** Zero financial hallucination; revenue, order counts, gross profits, and profit margins are computed using deterministic integer paise arithmetic.
- **Inventory & Reorder Assistance:** Automatic detection of slow-moving stock, holding cost calculations, and threshold-based supplier reorder recommendations.
- **Channel Margin Arbitrage:** Comparative unit economics showing net realized margins between direct sales (WhatsApp, Web) and third-party marketplaces.
- **WhatsApp Web Integration:** Bi-directional messaging gateway with strict number whitelisting, automated order lookups, and executive report dispatches.

---

### 4. Gnani AI & Gemini Intelligence Pipeline

```text
Merchant Voice (Kannada / Hindi / English)
         │
         ▼
[1] Gnani Prisma STT (v3.0) ──► Low-latency regional speech-to-text with indic-auto language identification
         │
         ▼
[2] Business Logic & SQLite  ──► Deterministic SQL analytics (sales, margins, inventory buffers in paise)
         │
         ▼
[3] Google Gemini Reasoning   ──► Structured retail prompt formatting, context memory, and proactive advice
         │
         ▼
[4] Gnani Timbre TTS (v3.0)  ──► High-clarity neural speech synthesis (Lakshmi & Avinash voice models)
         │
         ▼
Merchant Hears Spoken Response in Regional Audio
```

- **Gnani Prisma STT (v3.0):** Streaming and REST speech recognition with robust acoustic handling for Indian retail accents and shop background noise.
- **Gnani Timbre TTS (v3.0):** Natural regional voice synthesis using the `Lakshmi` (native Indic/Kannada) and `Avinash` (executive) neural voices.
- **Google Gemini:** Context-aware conversational reasoning, multi-turn pronoun resolution, polite error corrections, and proactive follow-up generation.

---

### 5. Technology Stack

- **Speech AI:** Gnani AI Prisma STT (v3.0), Gnani AI Timbre TTS (v3.0), Gnani Inya Agent Platform.
- **Reasoning:** Google Gemini API (`gemini-3.1-flash-lite-preview` / `gemini-flash-lite-latest`).
- **Backend:** FastAPI 0.111.0, Python 3.11+, SQLAlchemy 2.0 (asyncio), aiosqlite, Pydantic v2.
- **Frontend:** Next.js 16.3.4 (App Router, Turbopack), React 19, TypeScript 5, Tailwind CSS 4.
- **Payment & Standards:** Razorpay Test Mode integration, Model Context Protocol (MCP 2026).
- **Deployment:** Vercel (Frontend CDN) and Render (Containerized Python Backend).

---

### 6. Expected Impact for Small Merchants

Vyapar Mitra democratizes enterprise-grade business intelligence for neighborhood retailers. By removing English literacy and software barriers, merchants make faster inventory decisions, protect profit margins, avoid stockouts, and reclaim ownership of their customer relationships.

