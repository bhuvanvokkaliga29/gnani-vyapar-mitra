# Verified Assumptions & Ecosystem Intelligence

This document records every verified external fact, authoritative source, verification date, confidence level, and corresponding architectural implication for the **Merchant Policy Agent** (Razorpay AI Buildathon 2026 — Track 01).

---

## 1. Razorpay AI Buildathon & Track 01 Scope

### Fact 1.1: Track 01 Definition & Objective
- **Fact**: Track 01 is titled "AI Growth & Agentic Commerce". The objective is to build AI agents that grow a merchant’s revenue or enable them to be "transactable" by AI buyers end-to-end. Participants must use Razorpay test-mode APIs.
- **Source**: Razorpay AI Buildathon 2026 Official Track Documentation (`careerstn.com`, `coursejoiner.com`, `razorpay.com/buildathon-2026`).
- **Verification Date**: 2026-09-03
- **Confidence**: High (Verified via official announcements & track briefings).
- **Architecture Implication**: The agent must focus strictly on merchant-side revenue growth and AI-transactability. Any monetary transaction must run through Razorpay test-mode endpoints (`api.razorpay.com/v1`). It must not drift into fraud detection (Track 02), invoice collection/recovery (Track 03), or accounting reconciliation (Track 04).

### Fact 1.2: Buildathon Evaluation Criteria
- **Fact**: Submissions are judged across four primary dimensions: **Problem Taste**, **Build Quality**, **AI Judgment**, and **Failure Recovery**. Any monetary action must be explainable, bounded, gated, and audited.
- **Source**: Razorpay AI Buildathon Evaluation Guide.
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**: Hard deterministic boundaries must strictly fence LLM decisions. The LLM must never execute or commit funds directly. All actions must produce structured audit logs, with explicit handling for failure modes (timeouts, invalid JSON, out-of-bounds prices).

---

## 2. Razorpay API Capabilities & Constraints

### Fact 2.1: Orders API Contract
- **Fact**: Razorpay Orders API endpoint is `POST https://api.razorpay.com/v1/orders`.
  - Required parameters: `amount` (integer in smallest currency unit, e.g., paise for INR; no decimals), `currency` (ISO 4217, e.g., `"INR"`).
  - Optional parameters: `receipt` (string, max 40 characters), `notes` (key-value dictionary, max 15 key-value pairs, max 256 chars per key/value), `payment_capture` (integer: `1` for auto-capture, `0` for manual capture).
  - Authentication: HTTP Basic Auth with `key_id` as username and `key_secret` as password.
  - Immutability: An Order entity is immutable once created. Amount and currency cannot be updated.
- **Source**: Razorpay Official Orders API Documentation (`razorpay.com/docs/api/orders`).
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**: The application must deterministically compute total basket price in integer paise. The policy engine must map internal decision IDs to the `receipt` parameter (≤40 chars) to maintain audit lineage. To update a commercial offer, a new order must be created; existing orders cannot be mutated.

### Fact 2.2: Order Creation Safety vs. Idempotency
- **Fact**: While Razorpay APIs support idempotency headers in specific newer endpoints, generic `POST /v1/orders` should not be casually assumed to have universal HTTP idempotent replay semantics across all legacy gateways. Instead, Razorpay provides API retrieval for orders (`GET /v1/orders/{order_id}`) and order payments (`GET /v1/orders/{order_id}/payments`).
- **Source**: Razorpay API Error Handling & Reconciliation Guides.
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**: The Razorpay Adapter must never blindly retry order creation on timeout. If an order creation times out:
  ```text
  Application command
        ↓
  internal request_id / policy_decision_id
        ↓
  attempt Razorpay order creation
        ↓
  if timeout:
      reconcile using known identifiers / stored receipt
        ↓
  never blindly create another financial object
  ```

### Fact 2.3: Payments API & Test Mode Capture Flow
- **Fact**: Razorpay test mode does not use synthetic client-side mock events. Test mode mirrors live mode:
  - An authorized payment can be captured via `POST https://api.razorpay.com/v1/payments/{payment_id}/capture` with `amount` and `currency`.
  - Alternatively, setting `payment_capture: 1` on order creation automatically captures the authorized payment upon completion.
  - Test mode cards (e.g., `4012000000000002`) and simulated OTPs trigger real gateway state transitions to `captured`.
- **Source**: Razorpay Test Mode Documentation & Payments API Reference (`razorpay.com/docs/payments/test-card-details`).
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**: Acceptance tests must execute authentic Razorpay test-mode transactions resulting in `order.paid` and `payment.captured` states, rather than faking payment capture in memory.

### Fact 2.4: Webhook Signature Verification & Idempotency
- **Fact**: Razorpay signs webhook payloads using HMAC SHA256.
  - The signature is passed in header `X-Razorpay-Signature`.
  - It is computed by hashing the **exact raw request body buffer** with the merchant's configured Webhook Secret.
  - The header `X-Razorpay-Event-Id` provides a unique identifier per event transmission for deduplication.
  - Webhook events can arrive out of order (e.g., `payment.captured` before `order.paid`) or be delivered more than once.
- **Source**: Razorpay Webhooks Documentation (`razorpay.com/docs/webhooks`).
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**:
  - FastAPI webhook route must consume `Request.body()` raw bytes before any JSON parsing.
  - Every inbound webhook must be checked against a deduplication table indexed on `X-Razorpay-Event-Id`.
  - Transaction truth model: **Webhooks are the primary event signal; transaction state may be reconciled against Razorpay APIs when required.**

### Fact 2.5: Razorpay MCP (Model Context Protocol) Capabilities
- **Fact**: Razorpay exposes 35+ MCP tools covering payments, orders, payment links, refunds, settlements, and payouts.
- **Source**: Razorpay Developer Ecosystem & MCP Server Release Notes.
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**: Razorpay's native MCP server already exists for operational payment management. Our product’s value is **NOT** wrapping Razorpay APIs in MCP. Our product owns the merchant-side commercial policy intelligence:
  `Our Agent -> Deterministic Policy Engine -> Razorpay Adapter -> Razorpay APIs`.
  MCP is strictly an optional external tool interface, not a core runtime dependency for MVP.

---

## 3. Adjacent Agentic Commerce Ecosystem

### Fact 3.1: Emerging Agent-to-Agent Commerce Protocols
- **Fact**:
  - **Agentic Commerce Protocol (ACP)**: Introduced by OpenAI and Stripe (2025/2026) as an Apache 2.0 open standard for AI buyers to search, quote, and transact while merchants remain the merchant of record.
  - **Unified Autonomous Payments (UAP)**: NPCI initiative in India enabling AI agents to execute automated transactions within UPI rails (UPI Reserve Pay, spending limits).
  - **AP2 / x402**: Protocols standardizing machine-to-machine payment signaling and HTTP 402 "Payment Required" flows.
- **Source**: OpenAI / Stripe ACP Announcements, NPCI Industry Briefs, W3C Merchant Working Group.
- **Verification Date**: 2026-09-03
- **Confidence**: High.
- **Architecture Implication**: As AI buyers increasingly utilize ACP or API-based search queries to solicit quotes, merchants need an intelligent counter-agent to evaluate buyer constraints, formulate optimal commercial bundles, and quote prices that protect merchant margins.

---

## 4. Unverified Assumptions (Explicitly Documented)

### Assumption 4.1: Merchant Cost & Catalog Data Availability
- **Assumption**: Razorpay's core API does NOT provide merchant COGS (Cost of Goods Sold), supplier procurement costs, or wholesale inventory limits.
- **Verification Status**: Confirmed from API schemas. Razorpay stores Item entities for Invoices/Payment Links, but does not maintain merchant accounting cost sheets.
- **Confidence**: High.
- **Architecture Implication**: Product cost, margin floor, and inventory availability must be maintained within the application's internal merchant commerce store, not queried from Razorpay.

### Assumption 4.2: Real-World AI Buyer Adoption Volume
- **Assumption**: In 2026, direct programmatic AI-to-merchant purchases are growing rapidly but represent a fragmented volume compared to human browsing.
- **Verification Status**: Industry trend observation.
- **Confidence**: Medium.
- **Architecture Implication**: We must provide an **AI Buyer Lab** (controlled synthetic simulation environment) to stress-test policy learning under diverse buyer distributions, while maintaining a strict architectural wall between simulated results and verified Razorpay transaction outcomes.

---

## 5. Competitive Differentiation Hypothesis

| Capability | Generic Chatbots | Recommender Engines | AI SEO / Feed Optimizers | **Merchant Policy Agent (Our System)** |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Beneficiary** | Buyer / End User | Marketplace / Platform | Search Engine Indexers | **The Merchant** |
| **Decision Focus** | Conversational UI | Similar product matching | Keyword & schema tagging | **Commercial policy & profitable revenue** |
| **Guardrails** | System prompt instructions | Basic stock check | N/A | **Deterministic financial & margin engine** |
| **Transaction Ground Truth** | Chat state | Client cookies / Analytics | Page visits | **Razorpay test order + webhook reconciliation** |
| **Learning Mechanism** | Static prompt / RAG | Matrix factorization | Search ranking heuristics | **Empirical policy learning loop via real outcomes** |

### What We Are NOT Competing On:
1. We are **NOT** competing on natural language conversational checkout UI (Ray Smart Assist and chatbots handle this).
2. We are **NOT** competing on payment recovery or retry logic (Razorpay Agent Studio / Track 03 handles this).
3. We are **NOT** competing on chargeback dispute response (Razorpay Agent Studio handles this).
4. We are **NOT** competing on payment routing or fraud risk scoring (Razorpay core / Track 02 handles this).
