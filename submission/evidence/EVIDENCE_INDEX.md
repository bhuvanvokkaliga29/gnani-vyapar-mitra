# Evidence Index: Core Claims & Verification Mapping

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> **Release Candidate**: 1.0.0-rc  
> **Verification Baseline**: 926 Parent Tests (100% Passed) | 49 Phase 11 Adversarial Benchmarks (100% Passed)

This index maps every major architectural, commercial, safety, and learning claim made by the **Merchant Policy Agent** to its exact code implementation, authoritative automated test, and validation phase.

---

## Authoritative Claims to Evidence Matrix

| # | Core Claim | Mechanism / Evidence | Primary Files & Test Suites | Validation Phase |
| :- | :--- | :--- | :--- | :- |
| **1** | **LLM Cannot Directly Spend Money or Grant Unauthorized Discounts** | **Execution Authorization Boundary**: The LLM acts solely as a proposal generator (`PolicyProposal`). Hardcoded deterministic rule engines (`SafetyEvaluator`) enforce strict margin floors (25%) and budget ceilings before an authorization token is signed. The Razorpay Order creation occurs strictly downstream in the deterministic Execution Engine. | `services/execution/engine.py`<br>`services/safety/evaluator.py`<br>`tests/integration/test_phase11_2_golden_adversarial.py`<br>`tests/unit/test_safety_evaluator.py` | **Phase 5 / Phase 9 / Phase 11.2** |
| **2** | **Zero Negative-Margin Transactions (Margin Floor Enforced)** | **Integer Paise Math & Margin Floor**: Sub-margin buyer requests deterministically yield `NO_OFFER`. All prices, COGS, and margin calculations use integer paise arithmetic to eliminate floating-point drift. Even under adversarial buyer prompts, no order below margin floor is ever created. | `services/pricing/margin_engine.py`<br>`services/learning/reward_calculator.py`<br>`tests/integration/test_phase11_3_economic_adversarial.py`<br>`tests/unit/test_reward_calculator.py` | **Phase 6 / Phase 11.3** |
| **3** | **Negative Contribution is Preserved Without Distortion** | **Faithful Accounting**: When an order fails or is refunded, negative contribution (e.g. shipping/payment overhead) is recorded as-is without artificially clipping to zero. The agent penalizes poor policies proportionally. | `services/learning/reward_calculator.py`<br>`models/domain/outcome.py`<br>`tests/integration/test_phase11_3_economic_adversarial.py` | **Phase 6 / Phase 11.3** |
| **4** | **Duplicate Learning is Idempotent (Replay Immunity)** | **Event Ledger & Webhook Deduplication**: Repeated delivery of Razorpay payment webhooks or duplicate batch outcome updates are detected via unique event IDs. The LinUCB feature covariance matrix $A$ and vector $b$ are updated strictly once. | `services/learning/learner.py`<br>`services/razorpay/webhook_handler.py`<br>`tests/integration/test_phase11_4_learning_temporal_adversarial.py` | **Phase 8 / Phase 11.4** |
| **5** | **Strict Anti-Temporal Leakage (No Future Knowledge)** | **Temporal Ordering Boundary**: LinUCB contextual bandit model updates strictly ingest outcomes settled before timestamp $t$. Active proposals at time $t$ cannot observe concurrent or future transactions. | `services/learning/learner.py`<br>`services/learning/bandit.py`<br>`tests/integration/test_phase11_4_learning_temporal_adversarial.py` | **Phase 8 / Phase 11.4** |
| **6** | **Exploration is Strictly Budget-Bounded** | **Exploration Ceiling**: Contextual bandit exploration ($\epsilon$-greedy / upper-confidence bound) is capped at the merchant's configured maximum exploration budget (15%). Exploitation of proven policies is enforced for 85%+ of volume. | `services/learning/bandit.py`<br>`tests/integration/test_phase11_4_learning_temporal_adversarial.py`<br>`tests/unit/test_bandit.py` | **Phase 8 / Phase 11.4** |
| **7** | **Policy Promotion is Evidence-Gated & Governed** | **Statistical Significance Gate**: Candidate policies cannot be promoted to active status without meeting sample thresholds ($N \ge 100$), positive contribution margin delta, and safety sign-off. Early promotion requests deterministically fail with `INSUFFICIENT_SAMPLE_SIZE`. | `services/governance/manager.py`<br>`services/governance/evaluator.py`<br>`tests/integration/test_phase11_5_final_adversarial.py`<br>`tests/unit/test_governance.py` | **Phase 8 / Phase 11.5** |
| **8** | **Strict Multi-Tenant Isolation** | **Scoped Database & Cache Tenancy**: Every query, order, policy, and bandit state is indexed and filtered by `merchant_id`. Cross-tenant queries return 404/403 with an immediate security audit log. Merchant B (`merch_alpha`) cannot see Merchant A (`merch_atlas_travel`) data. | `services/database/session.py`<br>`services/api/routers/*.py`<br>`tests/integration/test_phase11_5_final_adversarial.py` | **Phase 4 / Phase 11.5** |
| **9** | **Inventory Depletion Halts Execution Atomically** | **Atomic Inventory Guard**: Concurrent access to stock-limited items uses atomic decrement with row-level locks. Reaching 0 inventory immediately triggers safety rejection, preventing overselling even during rapid AI buyer spikes. | `services/safety/inventory_guard.py`<br>`services/execution/engine.py`<br>`tests/integration/test_phase11_2_golden_adversarial.py` | **Phase 5 / Phase 11.2** |
| **10** | **Dashboard Telemetry Mathematically Reconciled with Authoritative DB** | **Direct Projection Verification**: The Merchant AI Control Center displays Opportunities (35), Executions (25), Paid (17), and Observed Contribution (₹19,529.05). Verified against authoritative SQL queries (`SELECT SUM()`, `SELECT COUNT(*)`) with zero divergence. | `tests/integration/test_dashboard_semantic_reconciliation.py`<br>`tests/integration/test_decision_detail_semantic_verification.py` | **Phase 12.1 / Phase 12.2** |
| **11** | **Razorpay Test Mode Integration with Real Signature Verification** | **Deterministic Gateway**: Real Razorpay Orders API calls with `order_*` IDs, Test Mode webhooks with HMAC-SHA256 signature verification, simulated payment links, and test payments. Zero live funds touched. | `services/razorpay/client.py`<br>`services/razorpay/webhook_handler.py`<br>`tests/integration/test_razorpay_client.py` | **Phase 1 / Phase 7 / Phase 11.1** |
| **12** | **Cross-Viewport Responsiveness & Zero Broken UI** | **Playwright End-to-End Suite**: 21 automated browser scenarios test Desktop (1440px, 1280px), Tablet (1024px), and Mobile (375px) viewports. Proves drawer animations, data tables, dropdowns, and metrics render flawlessly with zero overflow or console errors. | `frontend/e2e/*.spec.ts`<br>`submission/screenshots/`<br>`playwright.config.ts` | **Phase 10 / Phase 12.1** |

---

## Verification Artifact Locations

All evidence and test run artifacts are archived in the repository for full auditability:

- **Validation Report**: [VALIDATION_REPORT.md](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/submission/evidence/VALIDATION_REPORT.md)
- **Benchmark Results & Scenario Breakdown**: [BENCHMARK_RESULTS.md](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/submission/benchmark/BENCHMARK_RESULTS.md)
- **High-Resolution UI Screenshots**: [submission/screenshots/](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/submission/screenshots)
  - `01_overview_dashboard.png`: Main KPI metrics and real-time activity stream
  - `02_decisions_table.png`: Filterable AI commercial opportunities ledger
  - `03_decision_detail_drawer.png`: Multi-stage pipeline (Intent → Proposal → Safety → Razorpay Order → Payment)
  - `04_policies_management.png`: Active policies and governed candidate promotion gates
  - `05_learning_center.png`: LinUCB contextual bandit feature weights and sample distribution
- **Architectural Specification**: [architecture.md](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/submission/architecture.md)
- **Limitations & Disclosures**: [limitations.md](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/submission/limitations.md)
