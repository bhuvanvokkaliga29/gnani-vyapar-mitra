# Phase 0 Final Report: Product + Architecture Foundation

**Project**: Merchant Policy Agent  
**Buildathon**: Razorpay AI Buildathon 2026 (AI Builder Intern Track)  
**Assigned Track**: Track 01 — AI Growth & Agentic Commerce  
**Date**: September 3, 2026  
**Author**: Staff AI Engineer & Product Architect  

---

## 1. Executive Summary

Phase 0 establishes the engineering, architectural, and mathematical foundation for the **Merchant Policy Agent**. The primary objective of this phase is to ensure that the product boundary, economic formulas, deterministic guardrails, Razorpay test-mode transaction feedback loop, AI buyer simulation lab, failure modes, data models, and evaluation criteria are 100% verified, consistent, and locked before Phase 1 implementation begins.

The core thesis is locked:
> **As AI becomes the buyer in digital commerce, merchants lack a systematic way to understand why AI buyers select them or competitors and which commercial policies generate the highest profitable revenue. The Merchant Policy Agent learns a merchant-specific commerce policy by formulating candidate bundles, validating them against hard economic guardrails, executing test transactions via Razorpay, and using transaction outcomes to drive autonomous policy learning.**

All 21 required foundational specifications have been authored, verified against authoritative Razorpay documentation and agentic commerce standards (ACP, UAP), and formatted as an integrated technical specification in [`docs/`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs).

---

## 2. Problem

In traditional human-mediated commerce, conversion optimization targets visual aesthetics, emotional marketing copy, and visual cart upsell modals. 
In AI-mediated commerce, the purchaser is an autonomous algorithmic agent evaluating structured constraints (budget ceilings, delivery guarantees, technical specifications, and total bundle value vs. alternatives).

Merchants facing AI buyers encounter a ruinous **margin trap**:
- If they maintain static list prices, AI buyers route to competitor catalogs offering tighter constraint matches.
- If they discount blindly to capture volume, they erode gross margins and bleed profitability.

Merchants urgently require a **merchant-specific learning system** that determines which products, offers, bundles, and value propositions win AI buyer decisions while strictly safeguarding contribution margin.

---

## 3. Why Track 01

Track 01 (*AI Growth & Agentic Commerce*) challenges participants to build AI agents that grow a merchant's revenue or enable them to be transactable by AI buyers end-to-end.
The Merchant Policy Agent fits Track 01 precisely:
- **Revenue Growth**: Directly expands basket size (AOV) and conversion rate via intelligent bundling.
- **AI Transactability**: Exposes a structured quoting and transaction interface compatible with emerging agent protocols (ACP, AP2).
- **Hard Boundaries**: Adheres strictly to the required Buildathon bar: every financial action is bounded, explainable, and gated with full auditability.

---

## 4. Competitive Landscape

The commerce AI landscape is crowded with buyer-centric chatbots, generic product recommenders, and AI SEO taggers.
- **Buyer Chatbots (Perplexity, Ray Smart Assist)**: Optimize for consumer convenience and multi-merchant search.
- **Recommender Engines**: Optimize for platform click-through rate, ignoring merchant unit economics and margin floors.
- **AI SEO / Catalog Formatters**: Optimize for web crawler indexability, with zero transactional or pricing intelligence.
- **Razorpay Native Agent Studio**: Focuses on operational post-transaction workflows (chargeback dispute responder, subscription recovery).

---

## 5. Differentiation Hypothesis

Our differentiation hypothesis is:
$$\textbf{Merchant Policy Learning} + \textbf{AI-Buyer Experimentation} + \textbf{Deterministic Economic Guardrails} + \textbf{Razorpay Transaction Outcomes} + \textbf{Autonomous Learning Loop}$$

### What We Are Explicitly NOT Competing On:
1. We are **NOT** a conversational shopping chatbot.
2. We are **NOT** a visual checkout friction optimizer.
3. We are **NOT** an AI SEO or feed format optimizer.
4. We are **NOT** a payment failure recovery agent (Track 03).
5. We are **NOT** a fraud or risk detection agent (Track 02).

---

## 6. Product Definition & Contract

The product contract strictly partitions data ownership:
- **Merchant Inputs**: Catalog SKUs, unit base prices, unit COGS, physical inventory, and policy guardrails (margin floor %, discount ceiling %, max bundle size). Razorpay does not supply internal COGS; these are merchant-provided.
- **Agent Inputs**: Structured buyer intent, context catalog, and active experiment variant.
- **Agent Outputs**: Candidate commercial strategy (proposed items, prices in paise, bundle discount, qualitative value proposition, reasoning).
- **Engine Outputs**: Deterministic validation result (`is_approved`, calculated gross margin %, effective discount %, budget verification).
- **Outcome Contract**: Razorpay order ID, payment ID, captured status, and observed contribution in paise.

---

## 7. Agent Architecture

The system follows a modular monolith pattern (FastAPI + PostgreSQL + Next.js):
- **Unidirectional Gated Pipeline**:
  `AI Buyer Intent -> Policy Agent -> Structured Proposal -> Deterministic Policy Engine -> Razorpay Adapter -> Razorpay APIs -> Webhook Ingestion -> Outcome Store -> Policy Learning Loop`.
- **Lean Runtime**: No speculative infrastructure (no Kafka, no Kubernetes, no vector database, no multi-agent swarms).
- **MCP Evaluation**: Razorpay's 35+ MCP tools already exist; our product owns the merchant commercial policy logic. MCP is deferred as a non-core future demo interface.

---

## 8. Deterministic Policy Layer

# THE LLM CAN PROPOSE. IT CANNOT SPEND.

All financial actions, price arithmetic, and validations are executed in pure Python using integer paise:
1. **Gate 1 (Margin Floor)**: $\text{Gross Margin \%} \ge \text{Merchant Margin Floor}$.
2. **Gate 2 (Discount Ceiling)**: $\text{Effective Discount \%} \le \text{Max Discount Ceiling}$.
3. **Gate 3 (Buyer Budget)**: $\text{Total Basket Price} \le \text{Buyer Budget}$.
4. **Gate 4 (Inventory Check)**: $\text{Requested Quantity} \le \text{Current Stock}$.
5. **Gate 5 (Integer Math)**: Automatic recalculation of totals; zero reliance on LLM arithmetic.

---

## 9. Razorpay Integration

- **Transaction Truth Model**: Webhooks are the primary event signal; transaction state may be reconciled against Razorpay APIs when required (`GET /v1/orders/{id}` and `GET /v1/orders/{id}/payments`).
- **Order Creation Safety**: The adapter correlates each order with an internal `decision_id` passed via `receipt` (max 40 chars). If a timeout occurs on `POST /v1/orders`, the adapter reconciles with the local database and Razorpay API before ever creating a secondary order.
- **Authentic Capture Flow**: Test transactions reach real `order.paid` and `payment.captured` states in Razorpay test mode. No mock payment capture events are faked in memory.
- **Webhook Verification & Deduplication**: Raw request body bytes are verified via HMAC SHA256 against `X-Razorpay-Signature`. Deduplication is enforced atomically via PostgreSQL unique index on `X-Razorpay-Event-Id`.

---

## 10. AI Buyer Lab

The AI Buyer Lab provides a controlled synthetic simulation environment featuring six parameterized buyer personas:
1. `budget_sensitive`
2. `premium`
3. `gift_buyer`
4. `convenience_sensitive`
5. `performance_oriented`
6. `bundle_seeker`

> **Reporting Boundary**: Synthetic simulation results are tagged `is_simulated = TRUE` and are strictly partitioned from verified Razorpay transaction revenue.

---

## 11. Experimentation Framework

Experiments evaluate three variants:
- **CONTROL**: Single core SKU at catalog list price.
- **VARIANT A**: Core SKU + single high-affinity accessory.
- **VARIANT B**: Turnkey bundle + calibrated promotional incentive.

Traffic is allocated via an **Epsilon-Greedy multi-armed bandit** ($\epsilon = 0.20$) operating on observed contribution per shopper, switching from exploration to exploitation when sample size $N \ge 30$ per variant.

---

## 12. Metrics Framework

We strictly separate ex-ante expectation from ex-post observation:
- **Expected Contribution**:
  $$\text{Expected Contribution}(s \mid i) = P(\text{Purchase} \mid i, s) \times \mathbb{E}[\text{Contribution} \mid \text{Purchase}, s]$$
- **Observed Contribution**:
  $$\text{Observed Contribution} = \text{Captured Amount} - \text{Delivered COGS} - \text{Modeled Transaction Costs}$$
- **Supporting Metrics**: Conversion Rate, Average Order Value (AOV), Gross Margin %, and Revenue per Shopper (RPS).

---

## 13. Failure Recovery

The system details explicit automated recovery procedures for nine failure modes:
1. Malformed LLM output -> Fallback to catalog baseline.
2. Model downtime -> Fallback to catalog baseline.
3. Margin floor breach -> Deterministic rejection.
4. Discount ceiling breach -> Deterministic rejection.
5. Buyer budget overrun -> Deterministic rejection.
6. Out-of-stock SKU -> Bundle adjustment or baseline fallback.
7. Gateway timeout -> Receipt-based API reconciliation.
8. Duplicate webhook -> Idempotent HTTP 200 acknowledgment.
9. Database abort -> Transaction rollback and HTTP 503.

---

## 14. Security & Auditability

- **Secret Isolation**: Razorpay API keys and webhook secrets reside exclusively in backend environment variables.
- **Decision Lineage**: Every run records the raw query, extracted constraints, candidate JSON, qualitative reasoning, validation flags, Razorpay order ID, payment ID, and policy update in an append-only audit ledger.
- **Prompt Injection Defense**: Adversarial buyer queries cannot bypass pricing or margin rules because all constraints are evaluated by compiled deterministic code.

---

## 15. MVP Definition

The MVP proves **one complete closed loop**:
$$\text{Buyer Intent} \to \text{Policy Agent} \to \text{Deterministic Validation} \to \text{Razorpay Test Order} \to \text{Payment Capture} \to \text{HMAC Webhook} \to \text{Outcome Store} \to \text{Policy Learning}$$

All non-essential complexity (marketplaces, multi-tenant RBAC, Kafka, Redis, deep RL) is strictly deferred.

---

## 16. Risks & Mitigations

| Risk | Severity | Mitigation |
| :--- | :---: | :--- |
| **LLM Output Hallucination** | HIGH | Strict Pydantic v2 parsing with immediate fallback to static baseline on error. |
| **Silent Margin Erosion** | HIGH | Hard deterministic margin floor check ($M_{\text{floor}}$) prevents any order creation below threshold. |
| **Gateway Network Timeouts** | MEDIUM | Pre-allocated receipt ID correlation and API reconciliation before retrying. |
| **Webhook Packet Loss** | MEDIUM | Background polling reconciles unconfirmed orders via `GET /v1/orders/{id}/payments`. |
| **Synthetic Bias in Buyer Lab** | LOW | Strict labeling of simulated metrics; clear documentation of persona utility functions. |

---

## 17. Open Questions

1. **Webhook Tunneling in Local Development**: Will developers use ngrok, Webhook Relay, or a local proxy script for forwarding Razorpay test webhooks during evaluation? (Recommendation: Include lightweight ngrok / local webhook forwarder instructions in Phase 1).
2. **Default Margin Floor Standard**: Is 25% gross margin floor appropriate as the default merchant template? (Configurable per merchant in PostgreSQL).

---

## 18. Phase 1 Readiness

Phase 1 (*Razorpay Test-Mode Transaction Foundation*) is fully specified and ready to execute. Its acceptance criteria require zero application-level mocking:
```text
Create Test Order
        ↓
Complete Test Checkout / Test Payment
        ↓
payment/order reaches captured/paid state
        ↓
Webhook received
        ↓
Signature verified (HMAC SHA256)
        ↓
Event deduplicated (X-Razorpay-Event-Id)
        ↓
Outcome persisted
```

---

## PHASE 0 STATUS EVALUATION

| Criterion | Evaluation Standard | Status |
| :--- | :--- | :---: |
| **Problem clarity** | Precise, timely target persona and economic problem defined | **PASS** |
| **Track 01 fit** | Directly addresses AI growth, agentic commerce, and transactability | **PASS** |
| **Competitive boundary** | Explicit differentiation from chatbots, upsell engines, and SEO | **PASS** |
| **Architecture** | Minimal, robust modular monolith (FastAPI, Postgres, Next.js) | **PASS** |
| **Razorpay readiness** | Exact REST endpoints, HMAC verification, and reconciliation verified | **PASS** |
| **Agent boundary** | Absolute enforcement: *LLM can propose; it cannot spend* | **PASS** |
| **Economic model** | Separated expected vs observed contribution; 5 deterministic gates | **PASS** |
| **Experiment readiness** | 3-variant testbed, bandit allocation, and sample thresholds defined | **PASS** |
| **Failure recovery** | 9 comprehensive failure modes with automated fallbacks and audits | **PASS** |
| **MVP readiness** | Single closed-loop path strictly bounded; zero scope creep | **PASS** |

---

### FINAL RECOMMENDATION:
# READY FOR PHASE 1

### BLOCKERS:
**NONE.** All specifications are locked, verified, and internally consistent.

---

*(Per project instructions, execution stops here. Phase 1 implementation will begin only after Phase 0 review and approval).*
