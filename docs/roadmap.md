# Project Delivery Roadmap: Phase 0 through Phase 12

This document defines the sequential 13-phase implementation roadmap for the **Merchant Policy Agent**.

---

## Roadmap Overview

```text
[Phase 0] Product + Architecture Foundation  <-- WE ARE HERE
    ↓
[Phase 1] Razorpay Adapter + Test-Mode Transaction Loop
    ↓
[Phase 2] Merchant Commerce Model
    ↓
[Phase 3] Buyer Intent Extraction
    ↓
[Phase 4] Candidate Policy Generation
    ↓
[Phase 5] Deterministic Policy Engine
    ↓
[Phase 6] AI Buyer Lab
    ↓
[Phase 7] Experiment Engine
    ↓
[Phase 8] Policy Learning Loop
    ↓
[Phase 9] Merchant & Evaluation Dashboard
    ↓
[Phase 10] Failure Injection & Chaos Testing
    ↓
[Phase 11] Evaluation & Benchmark Reporting
    ↓
[Phase 12] Demo Hardening & Final Submission
```

---

## Phase Specifications

### Phase 0: Product + Architecture Foundation
- **Objective**: Establish complete, verified, and locked engineering specifications, data models, economics equations, and failure modes.
- **Dependencies**: None.
- **Deliverables**: 21 specification documents in `docs/`, repository structure scaffolding, Docker Compose configuration.
- **Acceptance Criteria**: All 21 documents internally consistent, verified against Razorpay APIs and Track 01 criteria; final Phase 0 status passes all rubrics.
- **Out of Scope**: Application source code, database migrations, live network requests.

### Phase 1: Razorpay Adapter + Test-Mode Transaction Loop
- **Objective**: Build the foundational transaction integration with Razorpay’s test-mode API.
- **Dependencies**: Phase 0.
- **Deliverables**: `services/razorpay` adapter, order creation client, HMAC webhook handler, event deduplication table.
- **Acceptance Criteria** *(Strictly as approved in Phase 0 review)*:
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
- **Out of Scope**: AI strategy generation, dynamic pricing, frontend UI.

### Phase 2: Merchant Commerce Model
- **Objective**: Implement the PostgreSQL data layer for merchants, product catalog, unit COGS, and baseline inventory.
- **Dependencies**: Phase 1.
- **Deliverables**: SQLAlchemy 2.0 models, Alembic migrations, CRUD service for merchant products and bundling affinity rules.
- **Acceptance Criteria**: Database tables successfully created; unit economics correctly persisted with integer paise; catalog querying passes unit tests.
- **Out of Scope**: LLM prompts, multi-tenant auth.

### Phase 3: Buyer Intent Extraction
- **Objective**: Ingest raw buyer natural-language queries or ACP requests and extract structured, typed constraints.
- **Dependencies**: Phase 2.
- **Deliverables**: Prompt templates for intent parsing, Pydantic schema validation for budgets, categories, and technical specs.
- **Acceptance Criteria**: Unstructured queries parse cleanly into typed constraints; adversarial queries fail gracefully without crashing.
- **Out of Scope**: Strategy generation, checkout.

### Phase 4: Candidate Policy Generation
- **Objective**: Build the LLM reasoning node that generates candidate commercial bundles and qualitative value propositions.
- **Dependencies**: Phase 3.
- **Deliverables**: Strategy generator node, catalog context injector, structured candidate proposal output.
- **Acceptance Criteria**: LLM produces valid JSON matching `CandidateCommercialStrategy` schema with coherent bundles and natural language explanations.
- **Out of Scope**: Financial execution, price mutation without validation.

### Phase 5: Deterministic Policy Engine
- **Objective**: Implement the hard deterministic guardrail layer that validates candidate strategies.
- **Dependencies**: Phase 4.
- **Deliverables**: `services/policy` engine checking margin floors, discount ceilings, buyer budget, and physical inventory.
- **Acceptance Criteria**: 100% of invalid candidate strategies (negative margins, excessive discounts, budget breaches, out-of-stock items) are deterministically rejected with audit logs.
- **Out of Scope**: Fuzzy heuristics, machine learning classification.

### Phase 6: AI Buyer Lab
- **Objective**: Create the controlled synthetic simulation testbed with 6 parameterized buyer personas.
- **Dependencies**: Phase 5.
- **Deliverables**: `services/experiments/lab`, persona generator (`budget_sensitive`, `premium`, etc.), simulated utility evaluator.
- **Acceptance Criteria**: Lab runs simulated scenarios across all 6 personas; outputs strictly marked `is_simulated = TRUE`.
- **Out of Scope**: Mixing simulated data with real transaction revenue.

### Phase 7: Experiment Engine
- **Objective**: Implement the three-variant testing framework (Control vs Variant A vs Variant B) and traffic routing.
- **Dependencies**: Phase 6.
- **Deliverables**: Multi-armed bandit traffic allocator, variant state tracker.
- **Acceptance Criteria**: Traffic distributes correctly; sample sizes and conversion counts tracked accurately per variant.
- **Out of Scope**: Off-policy counterfactual estimators.

### Phase 8: Policy Learning Loop
- **Objective**: Connect transaction outcomes to autonomous policy updates.
- **Dependencies**: Phase 7, Phase 1.
- **Deliverables**: Statistical update service adjusting bandit weights and variant recommendations based on observed contribution per shopper.
- **Acceptance Criteria**: When a variant demonstrates higher contribution per shopper with $N \ge 30$, traffic allocation shifts to exploit the winning strategy.
- **Out of Scope**: Deep reinforcement learning.

### Phase 9: Merchant & Evaluation Dashboard
- **Objective**: Build the Next.js UI for merchant visibility, audit exploration, and experiment tracking.
- **Dependencies**: Phase 8.
- **Deliverables**: Next.js App Router UI with Tailwind CSS, shadcn/ui, Recharts graphs, and audit drilldowns.
- **Acceptance Criteria**: Displays verified Razorpay revenue, gross margins, AOV, uplift charts, and full decision lineage traces.
- **Out of Scope**: End-user public storefront.

### Phase 10: Failure Injection & Chaos Testing
- **Objective**: Validate system resilience under intentional fault injection.
- **Dependencies**: Phase 9.
- **Deliverables**: Automated test suite executing all 9 chaos scenarios from `docs/failure-testing.md`.
- **Acceptance Criteria**: All 9 failure tests pass with safe fallback and immutable audit generation.
- **Out of Scope**: Chaos mesh cluster deployment.

### Phase 11: Evaluation & Benchmark Reporting
- **Objective**: Benchmark performance against Track 01 judging dimensions.
- **Dependencies**: Phase 10.
- **Deliverables**: Benchmark script measuring selection rate, AOV, margin %, and contribution per shopper across 200+ simulated buyer interactions.
- **Acceptance Criteria**: Clear demonstration of positive contribution uplift over static catalog pricing without violating margin floors.
- **Out of Scope**: Multi-merchant benchmark comparison.

### Phase 12: Demo Hardening & Final Submission
- **Objective**: Polish end-to-end user experience, document execution scripts, and verify submission packaging.
- **Dependencies**: Phase 11.
- **Deliverables**: Clean README, one-click `docker-compose up` setup, walkthrough recording, and submission bundle.
- **Acceptance Criteria**: Fresh clone on an isolated machine builds and runs complete transaction loop without manual intervention.
- **Out of Scope**: Post-hackathon enterprise multi-tenancy.
