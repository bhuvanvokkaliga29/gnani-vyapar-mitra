# Technology Decisions & Architecture Decision Records (ADRs)

This document records the technology stack evaluations, justifications, trade-offs, and explicit omissions for the **Merchant Policy Agent**.

---

## 1. Stack Summary Table

| Layer | Chosen Technology | Version / Standard | Primary Justification |
| :--- | :--- | :--- | :--- |
| **Backend Runtime** | Python | 3.11+ | Native ecosystem for AI reasoning, data validation, and financial math. |
| **API Framework** | FastAPI | 0.111+ | High-throughput asynchronous async/await, automated OpenAPI documentation. |
| **Validation Engine** | Pydantic | v2.7+ | C-core performance for JSON schema enforcement and strict type boundaries. |
| **Data Persistence** | PostgreSQL | 16 | Relational ACID guarantees, JSONB flexibility, strict transaction isolation. |
| **ORM / Migration** | SQLAlchemy + Alembic | 2.0+ (async) | Explicit typed queries, battle-tested connection pooling, automated schema migrations. |
| **HTTP Client** | httpx | 0.27+ | Async HTTP client with strict timeout configuration for Razorpay API calls. |
| **Logging & Audit** | structlog | 24.1+ | Structured JSON logs for full audit tracing across request lifecycles. |
| **Testing** | pytest + pytest-asyncio | 8.2+ | Robust async test runner for unit, integration, and failure injection suites. |
| **Frontend Framework**| Next.js | 14+ (App Router) | Server-side rendering, React Server Components, high performance dashboard. |
| **Language (UI)** | TypeScript | 5.4+ | End-to-end type safety aligned with backend Pydantic contracts. |
| **Styling & Components**| Tailwind CSS + shadcn/ui| Latest | Clean, modern design aesthetics with accessible component primitives. |
| **Data Visualization**| Recharts | 2.12+ | Composable SVG chart library for policy lift and experiment distribution views. |
| **Containerization** | Docker Compose | Compose v2 | Reproducible local development and single-command evaluation deployment. |

---

## 2. Architecture Decision Records (ADRs)

### ADR-01: Backend Framework — FastAPI over Django / Flask
- **Context**: The backend must handle concurrent buyer queries, coordinate LLM calls, run deterministic margin checks, and ingest Razorpay webhooks.
- **Decision**: Use **FastAPI** with **Pydantic v2**.
- **Rationale**:
  - Pydantic v2 provides compiled validation speed, crucial for validating candidate strategies against strict constraints.
  - Native asynchronous endpoints allow high concurrency while waiting for I/O (LLM inference and Razorpay HTTP requests).
  - Clean separation of concerns with dependency injection for database sessions and adapters.

### ADR-02: Orchestration — Minimal Explicit State Machine vs. LangGraph
- **Context**: Evaluating whether to adopt LangGraph or a generic agent framework.
- **Decision**: **Build a lean, explicit Python state machine**; do NOT include LangGraph in the MVP core runtime.
- **Rationale**:
  - The agent workflow follows a clean, single-agent 9-stage sequence (`INTENT -> CONTEXT -> GENERATE -> VALIDATE -> APPROVE/REJECT -> EXECUTE -> OBSERVE -> EVALUATE -> LEARN`).
  - LangGraph introduces heavy abstractions, hidden state mutations, and external dependencies that obscure failure boundaries.
  - In a financial system where **the LLM can propose but cannot spend**, hardcoded Python control flow with explicit validation checkpoints provides 100% transparent auditability and zero framework magic.
  - *Status*: Evaluation completed; minimal explicit state machine chosen.

### ADR-03: Model Context Protocol (MCP) — External Integration vs. Core Runtime
- **Context**: Evaluating whether Razorpay MCP tools should be the runtime execution driver.
- **Decision**: **Do NOT place MCP in the core execution path for MVP.**
- **Rationale**:
  - Razorpay already publishes 35+ MCP tools covering orders, payments, refunds, and payouts.
  - Our unique value is **NOT** wrapping Razorpay APIs into an MCP server. Our value is **Merchant-specific commercial policy learning**.
  - Placing an LLM behind MCP tools to execute orders would violate our core rule (*The LLM can propose, it cannot spend*).
  - The application owns the policy logic and interacts directly with Razorpay REST APIs via a deterministic adapter. MCP remains an optional future tool interface for third-party agent discovery.

### ADR-04: Redis Deferral — Stateless API + Postgres vs. Early Redis Cluster
- **Context**: Determining whether Redis is required for caching, sessions, or task queues.
- **Decision**: **Defer Redis.** The MVP operates purely with FastAPI and PostgreSQL.
- **Rationale**:
  - PostgreSQL 16 easily handles transaction rates of hundreds of requests per second for local evaluation and MVP scale.
  - Webhook deduplication is reliably enforced via a unique SQL index on `processed_webhook_events(event_id)`.
  - Adding Redis introduces an extra stateful dependency and split-brain recovery failure modes without providing measurable value for the Buildathon MVP.
  - Redis will only be introduced if background job queueing exceeds synchronous database capacity in Phase 7+.

### ADR-05: Webhook Verification — Raw Byte Processing
- **Context**: Verifying Razorpay's HMAC SHA256 signature in FastAPI.
- **Decision**: Read raw `Request.body()` bytes directly in the webhook route before any parsing.
- **Rationale**:
  - Razorpay webhook verification fails if JSON serializers alter whitespace, key ordering, or character encoding.
  - Using raw binary buffers ensures exact cryptographic matching with `X-Razorpay-Signature`.
