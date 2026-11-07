# Minimum Viable Product (MVP) Specification

This document strictly defines the boundaries, single execution path, and success criteria for the **Merchant Policy Agent MVP**.

---

## 1. The Single MVP Path: The Closed Commercial Loop

The MVP has exactly **one** primary deliverable: prove one unbroken, trustworthy, and auditable commercial learning loop from AI buyer intent to Razorpay transaction confirmation and policy adaptation.

```text
               1. Buyer says what they want (natural language / ACP query)
                                    ↓
                       2. Structured Intent Extraction
                                    ↓
                       3. Merchant Policy Agent
                                    ↓
                   4. Candidate Commercial Strategy Proposal
                                    ↓
                   5. Deterministic Guardrail Validation
                                    ↓
                   6. Razorpay Test Order Creation (POST /v1/orders)
                                    ↓
                   7. Complete Test Payment (captured state)
                                    ↓
                   8. Signed Webhook Ingestion (HMAC SHA256)
                                    ↓
                   9. Outcome Recorded & Persisted in DB
                                    ↓
                   10. Experiment Contribution Metric Calculated
                                    ↓
                   11. Autonomous Policy Insight & Learning Update
                                    ↺
```

---

## 2. In-Scope MVP Capabilities

| Domain | In-Scope MVP Capability | Implementation Standard |
| :--- | :--- | :--- |
| **Catalog & Economics** | Single merchant with a focused 10-SKU catalog (e.g., premium coffee equipment). | Explicit base prices, unit COGS, and active inventory in PostgreSQL. |
| **Merchant Rules** | Single active policy profile: Margin floor 25%, Discount ceiling 20%, Max bundle size 3. | Hardcoded or database-backed configuration enforced deterministically. |
| **Agent Reasoning** | Single prompt pipeline extracting constraints and formulating bundle proposals. | Strict JSON schema output via Pydantic v2. |
| **Guardrail Engine** | Pure Python integer arithmetic (paise) validating all 5 business gates. | 100% test coverage on rejection branches. |
| **Razorpay Integration**| Test-mode order creation, test checkout execution, webhook signature verification, and deduplication. | Authentic `rzp_test_...` credentials; no fake client-side capture mocks. |
| **Experimentation** | 3 variants: Control (single product) vs. Variant A (cross-sell) vs. Variant B (bundle). | Epsilon-greedy multi-armed bandit tracking contribution per shopper. |
| **User Interface** | Next.js dashboard showing real-time metrics, audit logs, and AI Buyer Lab simulator. | Clean Tailwind CSS + shadcn/ui interface with interactive charts. |

---

## 3. Explicitly Out-of-Scope for MVP

The following items are strictly deferred to post-MVP to prevent scope creep:
- ❌ Third-party marketplace integrations (Shopify, Amazon, WooCommerce syncing).
- ❌ Multi-tenant user permission hierarchies and role-based access control (RBAC).
- ❌ Complex distributed messaging brokers (Kafka, RabbitMQ).
- ❌ Vector database semantic search (pgvector or Pinecone).
- ❌ Live production credit card charging or banking settlements.
- ❌ Autonomous advertising spend or social media campaign creation.
- ❌ Multi-currency international forex calculations.
- ❌ Complex deep reinforcement learning models requiring millions of iterations.

---

## 4. MVP Definition of Success

The MVP is deemed successful if and only if:
1. An incoming AI buyer query generates a validated bundle offer that stays within the buyer's budget and exceeds the merchant's margin floor.
2. A real test-mode Razorpay order is registered with the internal decision ID in the `receipt` parameter.
3. Test payment capture dispatches an authentic webhook event (`order.paid` / `payment.captured`).
4. The webhook is cryptographically verified via HMAC SHA256 and deduplicated via `X-Razorpay-Event-Id`.
5. Realized contribution is accurately calculated and credited to the winning variant in the policy store.
6. The entire sequence is visible in the audit explorer with zero unhandled exceptions.
