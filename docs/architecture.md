# System Architecture Specification

This document defines the system topology, component interactions, API boundaries, and communication paths for the **Merchant Policy Agent**.

---

## 1. Minimal Architectural Philosophy

The architecture adheres strictly to **Rule 8**: *Prefer simple architecture over speculative infrastructure*.
- **No Kafka / RabbitMQ**: Synchronous HTTP with database transactions and lightweight background tasks are sufficient for MVP.
- **No Kubernetes / Distributed Clusters**: Single-node Docker Compose handles API, Web, and Database.
- **No Vector Database**: Relational schema with standard B-tree indexes and JSONB metadata handles all catalog queries and buyer intent matching.
- **No Multi-Agent Swarms**: A single, coherent Merchant Policy Agent paired with a Deterministic Policy Engine eliminates emergent coordination failures.
- **No MCP in Core Runtime**: The application owns its policy logic and communicates directly with Razorpay REST APIs via a clean Python adapter.

---

## 2. Phase 2: Deterministic Commerce Model Boundary

The Merchant Commerce Model is the inviolable deterministic knowledge layer governing commercial truth:

```text
                  Merchant
                     │
                     ▼
             Commerce Model
                     │
       ┌─────────────┼─────────────┐
       │             │             │
       ▼             ▼             ▼
    Catalog       Economics     Constraints
       │             │             │
       └─────────────┼─────────────┘
                     ▼
          Merchant Commerce Context
                     │
                     ▼
          Future Policy Agent (Phase 3+ dependency)
```

- **Catalog**: Products, integer paise pricing, COGS, physical inventory counts.
- **Economics**: Deterministic gross profit, exact decimal margin percentage, and basket guardrails.
- **Constraints**: Minimum margin floors, promotional discount ceilings, and target AOV.
- **Merchant Commerce Context**: Strongly-typed single boundary object (`GET /api/v1/merchants/{id}/commerce-context`).

---

## 3. Phase 3: Buyer Intent Engine Boundary

The Buyer Intent Engine is the machine-readable comprehension layer translating untrusted natural language into structured `BuyerIntent` facts:

```text
Natural Language Buyer Utterance
              │
              ▼
   Intent Extractor Engine
(Injection defense, normalizer, semantic validator)
              │
              ▼
         BuyerIntent
(Requirements, preferences, budget, exclusions, unknowns)
              │
              ▼
    Future Policy Agent (Phase 4)
              │
   (Evaluates against MerchantCommerceContext)
              ▼
Candidate Commercial Strategies
```

- **Separation Invariant**: Understanding ONLY. Phase 3 does NOT select products, rank items, or apply merchant discounts.
- **Zero False Inference**: Attributes not explicitly stated remain `unknown`.
- **Requirements vs Preferences**: Hard constraints and soft desires are stored in separate schema collections.
- **API Surface**: `POST /api/v1/intent/parse`.

---

## 4. End-to-End System Topology

```text
                    ┌────────────────────────────────────────┐
                    │              Next.js UI                │
                    │      (App Router, TypeScript,          │
                    │       Tailwind CSS, Recharts)          │
                    └───────────────────┬────────────────────┘
                                        │ HTTP / JSON
                                        ▼
                    ┌────────────────────────────────────────┐
                    │              FastAPI API               │
                    │       (Pydantic v2, structlog)         │
                    └───────────────────┬────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│ Commerce Engine  │          │   Policy Agent   │          │ Experiment Lab   │
│                  │          │                  │          │                  │
│ • Catalog Store  │          │ • Prompting Node │          │ • Synthetic AI   │
│ • Unit COGS      │          │ • Strategy Gen   │          │   Buyer Personas │
│ • Inventory Svc  │          │ • Natural Lang   │          │ • Variant Alloc  │
│ • Bundle Rules   │          │   Explanation    │          │ • Benchmark Sim  │
└─────────┬────────┘          └─────────┬────────┘          └─────────┬────────┘
          │                             │                             │
          └─────────────────────────────┼─────────────────────────────┘
                                        ▼
                    ┌────────────────────────────────────────┐
                    │       Deterministic Policy Engine      │
                    │                                        │
                    │ • Margin Floor Check (≥ min %)         │
                    │ • Discount Ceiling Check (≤ max %)     │
                    │ • Buyer Budget Verification            │
                    │ • Real-time Inventory Audit            │
                    │ • Integer Arithmetic in Paise          │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │           Razorpay Adapter             │
                    │                                        │
                    │ • Internal Request Correlation         │
                    │ • Order Creator (POST /v1/orders)      │
                    │ • Timeout Reconciler (GET /v1/orders)  │
                    │ • Webhook Ingestion & HMAC SHA256      │
                    │ • Event Deduplication (X-Event-Id)     │
                    └───────────────────┬────────────────────┘
                                        │
                           HTTPS (Basic Auth: key_id/secret)
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │           Razorpay Test APIs           │
                    │    https://api.razorpay.com/v1         │
                    └───────────────────┬────────────────────┘
                                        │
                         Test Payment State Transitions
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │          Inbound Webhook HTTP          │
                    │         (X-Razorpay-Signature)         │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │        Outcome & Feedback Store        │
                    │              (PostgreSQL)              │
                    │                                        │
                    │ • Transaction Outcomes                 │
                    │ • Policy Learning Updates              │
                    │ • Immutable Audit Logs                 │
                    └───────────────────┬────────────────────┘
                                        │
                                        └───────────────── (Feedback Loop) ↺
```

---

## 3. Component Breakdown & Responsibilities

### 3.1 Next.js Web UI (`apps/web`)
- **Role**: Merchant Dashboard and AI Buyer Lab simulator interface.
- **Key Views**:
  - *Policy Performance Dashboard*: Verified Razorpay revenue, Gross Margin %, Average Order Value, and Expected Contribution per Shopper.
  - *Experiment Control Room*: Live A/B variant tracking, win rates, and bandit allocation sliders.
  - *Audit & Decision Explorer*: Inspect why the agent approved or rejected specific candidate strategies for particular buyer queries.
  - *AI Buyer Lab Playground*: Run controlled scenario tests across 6 buyer personas without polluting verified transaction metrics.

### 3.2 FastAPI Application Layer (`apps/api`)
- **Role**: High-performance asynchronous API layer.
- **Key Modules**:
  - `/api/v1/intent`: Ingests buyer intent from external agents or lab simulator.
  - `/api/v1/policies`: Merchant policy configuration and constraint management.
  - `/api/v1/experiments`: Experiment definition and variant assignment.
  - `/api/v1/orders`: Deterministic order generation.
  - `/api/v1/webhooks/razorpay`: Raw-body HMAC verification and idempotent event ingestion.
  - `/api/v1/reconciliation`: Asynchronous order and payment status reconciliation against Razorpay APIs.

### 3.3 The Core Subsystems (`services/`)
1. **`services/commerce`**: Manages merchant catalog data, SKU associations, current inventory levels, and unit COGS.
2. **`services/agent`**: Formulates candidate strategies using structured LLM prompts. Produces candidate products, bundle discounts, and qualitative explanations.
3. **`services/policy`**: Purely deterministic validation engine. Audits candidate bundles against margin floors, discount ceilings, and inventory. Recalculates all arithmetic.
4. **`services/experiments`**: Manages experimental variant routing (Control vs Variant A vs Variant B) and evaluates statistical performance.
5. **`services/razorpay`**: The transaction gateway adapter. Translates approved strategies into Razorpay Orders, enforces internal request ID correlation, handles timeouts via API retrieval, and processes signed webhooks.

### 3.4 Data Persistence Layer (`PostgreSQL 16`)
- Single PostgreSQL database holding:
  - Relational entities (`merchants`, `products`, `orders`, `payments`).
  - Audit event logs (`audit_events`, `agent_decisions`).
  - Webhook deduplication records (`processed_webhook_events`).
  - Experiment variant performance metrics (`experiment_variants`, `policy_learning_records`).

---

## 4. Transaction Truth & Reconciliation Flow

```text
1. Policy Approved ──> 2. Insert DB Order Record (status: PENDING, internal_receipt: dec_123)
                            │
                            ▼
                       3. POST /v1/orders to Razorpay
                            │
            ┌───────────────┴───────────────┐
            ▼ [SUCCESS: order_id]           ▼ [TIMEOUT / NETWORK ERROR]
       Update DB with order_id        Do NOT re-create order!
            │                         GET /v1/orders with receipt correlation
            ▼                         Reconcile before returning error
       Return to AI Buyer
            │
            ▼
       Buyer executes payment
            │
            ▼
       4. Razorpay Webhook Dispatched (order.paid)
            │
            ▼
       5. FastAPI Webhook Handler verifies HMAC SHA256
            │
            ▼
       6. Check X-Razorpay-Event-Id in DB
          • If already seen: Return 200 OK (idempotent skip)
          • If new: Insert event_id, update Order/Payment to CAPTURED
            │
            ▼
       7. Calculate Observed Contribution & Trigger Policy Learning Loop
```
