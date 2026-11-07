# 🔌 Vyapar Mitra — Integration Gap & Technical Requirements Report
**Competition**: The Great Indian AI Internship Challenge 2026 (Gnani AI)  
**Document**: API Integration Gaps, Protocol Specifications & Credit Budgeting  
**Author**: Senior Voice AI Engineer  

---

## 1. Gnani AI Integration Gap Analysis

### A. Gnani Prisma — Speech-to-Text (STT)
| Parameter | Current State | Required Target State |
| :--- | :--- | :--- |
| **API Client** | None | Dedicated async Python client `services/voice/gnani_stt_client.py` |
| **Endpoint Structure** | Not configured | Gnani Speech-to-Text REST / WebSocket endpoint (`/api/v1/stt` or provider-documented URL) |
| **Authentication** | None | Header: `token: <GNANI_API_KEY>` or `Authorization: Bearer <GNANI_API_KEY>` + `access-token` |
| **Audio Format Ingestion** | Not supported | 16kHz Mono WAV / FLAC / WebM Opus recorded from browser microphone |
| **Supported Languages** | None | `kn-IN` (Kannada), `hi-IN` (Hindi), `en-IN` (Indian English), and Code-Mixed variants |
| **Audio File Size Limits** | None | Validate file size $\le 10$MB, duration $\le 60$s to conserve API credits |
| **Fallback Mechanism** | None | If Gnani API fails/unreachable, fallback gracefully to offline rule-based parser or browser recognition |

### B. Gnani Timbre — Text-to-Speech (TTS)
| Parameter | Current State | Required Target State |
| :--- | :--- | :--- |
| **API Client** | None | Dedicated async Python client `services/voice/gnani_tts_client.py` |
| **Endpoint Structure** | Not configured | Gnani Timbre REST endpoint (`/api/v1/tts` or provider-documented URL) |
| **Authentication** | None | Same unified or separate Gnani API credentials as configured |
| **Voice Persona** | `edge-tts` / `gTTS` | Natural Indian voices supporting Kannada, Hindi, and Indian English accents |
| **Audio Output Format** | None | Return MP3 / WAV audio binary or base64 data URI to frontend |
| **Player Controls** | None | HTML5 Audio player with Play, Pause, Replay, and Waveform Visualizer |
| **Fallback Mechanism** | `edge-tts` | If Gnani Timbre returns error or budget exhausted, fall back to `edge-tts` cleanly |

### C. Credit Budget Optimization Plan (5,000 Credits)
1. **Developer Guard**: Implement a local test mode fixture (`GNANI_USE_LOCAL_MOCK=true` when developing UI layouts) so developers do not burn credits during CSS tweaking.
2. **Audio Truncation**: Restrict voice input queries to 15 seconds max. Most merchant queries ("How much did I sell today?", "What is my top product?") take 3–5 seconds of speech.
3. **Response Conciseness**: Keep spoken responses to 2–3 succinct sentences (40–60 words) to minimize TTS synthesis cost. Full detailed numbers are rendered in the visual card.
4. **Caching Non-Sensitive Audio**: Cache common static voice responses (such as the initial greeting) in memory or disk.

---

## 2. Google Gemini API Integration Gap Analysis

| Dimension | Current Implementation | Target Implementation |
| :--- | :--- | :--- |
| **Target Router** | `services/policy/llm_client.py` | Create dedicated `services/agent/doctor_advisor.py` |
| **Primary Task** | Proposing policy discount candidates | Acting as the conversational AI Business Advisor |
| **Prompt Engineering** | B2B buyer discount schemas | Multilingual retail advisor understanding retail metrics, margins, and growth |
| **Tool Calling / Data Retrieval** | Static payload injection | Structured backend tools (`get_daily_sales`, `get_inventory_health`, etc.) |
| **Financial Guardrails** | Deterministic code validates | Deterministic code calculates values before LLM sees them; LLM cannot alter numbers |
| **Fallback Handling** | Returns `None` on timeout | Returns pre-compiled deterministic business diagnosis |

---

## 3. Database & Business Data Gaps

| Entity | Current Count | Target Count | Key Attributes Needed |
| :--- | :--- | :--- | :--- |
| **Vastram Products** | 8 SKUs | **50–80 SKUs** | SKU, Name, Category (Shirts, Trousers, Kurtis, T-Shirts, Blazers, Accessories), Cost Price, Selling Price, Stock Qty, Minimum Threshold, Margin % |
| **Orders** | ~35 (Oct 17 only) | **300+ across 30 days** | Reconciled daily totals, realistic channel splits (WhatsApp 45%, Amazon 30%, D2C Web 25%), AOV ~₹2,499 |
| **Payments** | ~35 | **300+ matching orders** | UPI (PhonePe, GPay, Paytm), Cards, Netbanking, COD |
| **Diagnostic Findings** | Hardcoded (3) | Dynamic (5+) | Dead Stock, Margin Leakage, Underpriced SKUs, High Return Rates, Stockout Warnings |
| **Merchant Actions** | 1 (static) | Interactive (5+) | Price adjustments, bundle creation, reorder requests, clearance promotions |

---

## 4. Request a Callback Subsystem Requirements

Gnani AI provides speech recognition and synthesis; it does **not** provide outbound PSTN/telephony routing.
To build a realistic, production-ready "Request a Callback" feature:
1. **Data Model**: Create `MerchantCallbackRequest` table tracking:
   - `id`: Unique callback request ID (`cb_...`)
   - `merchant_id`: Tenant ID (`merch_atlas_travel` / Vastram)
   - `phone_number`: Verified merchant phone (`+919113960498`)
   - `preferred_language`: `kn`, `hi`, or `en`
   - `topic`: Sales summary, inventory reorder, or pricing strategy
   - `scheduled_time`: Immediate or chosen time window
   - `status`: `PENDING`, `DISPATCHED`, `COMPLETED`, `CANCELLED`
   - `notes`: AI call summary and recommended follow-up actions
2. **Telephony Bridge**: Implement an abstraction layer supporting Twilio Voice or Exotel, with a clear simulation state when third-party telephony credentials are not yet configured.
3. **UI Experience**: An intuitive drawer in the Doctor interface with phone confirmation, language selector, topic selection, and status badge.

