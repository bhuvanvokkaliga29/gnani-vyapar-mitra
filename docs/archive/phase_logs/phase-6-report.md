# Phase 6 Completion & Hardening Report: AI Buyer Lab

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 — Track 01)  
**Phase**: Phase 6 — AI Buyer Lab: Controlled Machine-Buyer Simulation & Offer Selection Environment  
**Status**: **COMPLETE, REFINED, VERIFIED, BENCHMARK CERTIFIED, CONTRACT FROZEN (`buyer-selection/v1`)**  
**Core Invariant Preserved**: **SIMULATED BUYER CHOICE $\ne$ REAL CUSTOMER CONVERSION**  
**Hard Stop Condition**: Maintained. Phase 7 has **NOT** been started.

---

## 1. Files Changed and Created

| File | Status | Description |
|:---|:---:|:---|
| [`services/buyer_lab/schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/schemas.py) | **New** | Pydantic v2 schemas for `BuyerOffer`, `BuyerSelectionResult`, `RejectedOfferTrace`, `DecisionStepTrace`, and enums. |
| [`services/buyer_lab/errors.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/errors.py) | **New** | Domain exceptions: `BuyerLabError`, `IneligibleOfferError`, `MalformedOfferError`. |
| [`services/buyer_lab/filter.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/filter.py) | **New** | Deterministic eligibility filter enforcing availability, currency, budget ceiling, hard specs, and explicit exclusions. |
| [`services/buyer_lab/evaluator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/evaluator.py) | **New** | Preference evaluator, persona weight calculator, and deterministic tie-breaker. |
| [`services/buyer_lab/simulator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/simulator.py) | **New** | Central coordinator managing sanitization, filtering, short-circuit, evaluation, and trace generation. Preserves BuyerIntent immutability. |
| [`services/buyer_lab/competitors.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/competitors.py) | **New** | Standard synthetic competitor fixtures (`Apex Luggage`, `Budget Pack Tech`, `Nordic Gear`, `Classic Leatherworks`). |
| [`services/buyer_lab/benchmark.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/benchmark.py) | **New** | 50-scenario golden benchmark suite. |
| [`services/buyer_lab/__init__.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/__init__.py) | **New** | Module exports. |
| [`apps/api/routers/buyer_lab.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/routers/buyer_lab.py) | **New** | FastAPI endpoint `POST /api/v1/buyer-lab/simulate`. |
| [`apps/api/main.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/apps/api/main.py) | **Modified** | Registered `buyer_lab.router` in FastAPI application. |
| [`tests/unit/test_buyer_lab_schemas.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_buyer_lab_schemas.py) | **New** | Schema invariant tests and extra field prohibition tests. |
| [`tests/unit/test_buyer_lab_filter.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_buyer_lab_filter.py) | **New** | Hard requirement, exclusion, and budget filtering tests. |
| [`tests/unit/test_buyer_lab_evaluator.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_buyer_lab_evaluator.py) | **New** | Preference evaluation, persona weights, and deterministic tie-breaking tests. |
| [`tests/unit/test_buyer_lab_benchmark.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_buyer_lab_benchmark.py) | **New** | Execution of all 50 golden benchmark scenarios (100% compliance). |
| [`tests/unit/test_buyer_lab_hardening.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/unit/test_buyer_lab_hardening.py) | **New** | 14 targeted hardening tests: hard constraint dominance, intent immutability, merchant neutrality, prompt-injection survival, and trace consistency. |
| [`tests/integration/test_buyer_lab_api.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_buyer_lab_api.py) | **New** | Integration tests for `POST /api/v1/buyer-lab/simulate`. |
| [`tests/integration/test_buyer_lab_security.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_buyer_lab_security.py) | **New** | Static AST boundary tests, prompt injection tests, and financial injection rejection. |
| [`tests/integration/test_buyer_lab_reproducibility.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_buyer_lab_reproducibility.py) | **New** | 10x repeated-run stability tests. |
| [`docs/phase-6-buyer-lab-contract.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-6-buyer-lab-contract.md) | **New** | Formal Buyer Lab contract specification. |
| [`docs/phase-6-buyer-model.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-6-buyer-model.md) | **New** | Decision hierarchy, hard constraint dominance, and persona mechanics. |
| [`docs/phase-6-evaluation.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-6-evaluation.md) | **New** | Evaluation matrix and scientific distinctions. |
| [`docs/phase-6-security.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-6-security.md) | **New** | Threat model, Data vs Instruction invariant, and prompt-injection mitigations. |
| [`docs/phase-6-benchmark.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-6-benchmark.md) | **New** | Golden benchmark catalog. |
| [`docs/phase-6-report.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/phase-6-report.md) | **New** | Executive completion and refinement report. |

---

## 2. AI Buyer Lab Architecture

```text
BuyerIntent v1 (from Phase 3)
      │
      ▼
POST /api/v1/buyer-lab/simulate
      │
      ▼
BuyerSimulator
      ├── Step 0: Prompt-Injection Sanitization (Defense-in-depth regex neutralization)
      ├── Step 1: Availability & Currency Filter (In-stock, currency matching)
      ├── Step 2: Budget Ceiling Filter (offer.price_paise <= max_amount_paise)
      ├── Step 3: Hard Requirement Filter (Numeric GTE/LTE, string CONTAINS/EQ)
      ├── Step 4: Explicit Exclusion Filter (Zero tolerance for excluded attributes)
      │
      ├── [If 0 Offers Survive] ──> NO_ELIGIBLE_OFFER (selected_offer_id = None)
      │
      ├── Step 5: Soft Preference Evaluation (Warranty, delivery speed, accessories)
      ├── Step 6: Persona Weighting (Soft utility weighting strictly among eligible offers)
      └── Step 7: Deterministic Tie-Breaker (Preference count -> Price -> Alphabetical offer_id)
      │
      ▼
BuyerSelectionResult v1 (buyer-selection/v1)
```

---

## 3. BuyerSelectionResult Contract (`buyer-selection/v1`)
- Explicitly separates `candidate_offer_ids`, `eligible_offer_ids`, and `rejected_offers`.
- Rejection traces contain exact machine-readable codes (`OfferRejectionCode`).
- Selection reasons categorized under `SelectionTaxonomy`.
- Includes step-by-step `decision_trace`.
- Prohibits fake numerical conversion probabilities.

---

## 4. Offer Contract (`BuyerOffer`)
- Contains **only buyer-visible data**: price in paise, availability, specifications, warranty, delivery timeframe, bundle components, and incentives.
- Strictly forbids internal merchant metadata: `cogs_paise`, `margin_percent`, `merchant_objective`, `policy_score`, and `execution_approval` (`extra="forbid"`).

---

## 5. Buyer Decision Hierarchy & Hard Constraint Dominance

```text
1. Hard Requirements
2. Explicit Exclusions
3. Budget Ceiling
4. Eligible Offer Set
5. Soft Preferences
6. Persona Weighting
7. Buyer-Visible Value Comparison
8. Deterministic Tie-Breaks
```

> **Mandatory Invariant**: Persona weighting can **NEVER** override BuyerIntent hard constraints, exclusions, or budget limits.
> The persona operates exclusively on Step 6 over offers that have already passed Steps 1–3.

---

## 6. Hard vs. Soft Constraint Handling
- **Hard Constraints**: Immediate disqualification upon failure (`HARD_REQUIREMENT_VIOLATED`, `EXCLUDED_BY_BUYER`, `BUDGET_EXCEEDED`).
- **Soft Preferences**: Evaluated only on surviving eligible offers. High strength preferences (`PreferenceStrength.EXPLICIT`) receive double weight.

---

## 7. Tie-Break Semantics
Deterministic tie-breaking hierarchy:
1. Higher count of satisfied explicit preferences.
2. Lower buyer-visible total price in paise.
3. Alphabetical `offer_id` order (e.g. `off_alpha` beats `off_beta`).
Zero randomness. Zero merchant bias.

---

## 8. No-Eligible-Offer Behavior
When all candidate offers fail hard constraints, the system returns `selected_offer_id = None` and `selection_reasons = [NO_ELIGIBLE_OFFER]`. The simulator never settles or relaxes constraints. No persona can force a winner when all offers are invalid.

---

## 9. Prompt-Injection Defense: Data vs. Instructions Invariant
- **Offer Content = DATA; Offer Content $\ne$ INSTRUCTIONS.**
- Regex sanitization serves as defense-in-depth.
- The primary boundary is deterministic code: Even if an adversarial instruction variant survives sanitization, deterministic Python logic evaluates strings as literal passive data. Commands cannot alter numeric comparisons, budget calculations, or exclusion checks.

---

## 10. Synthetic Competitor Handling
Standard synthetic competitors (`Apex Luggage`, `Budget Pack Tech`, `Nordic Gear`, `Classic Leatherworks`) are tagged `is_synthetic = True` and kept completely segregated from merchant production data.

---

## 11. Benchmark Size and Coverage
- **50 Golden Benchmark Scenarios** implemented in [`services/buyer_lab/benchmark.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/buyer_lab/benchmark.py).
- Covers hard constraints (10), cheap-but-invalid (8), exclusions (8), soft preferences (8), no-eligible-offer (6), tie-breaks (5), and security injections (5).
- **100% compliance across all 50 predefined scenarios.**

---

## 12. Evaluation Metrics

| Metric | Target | Observed | Result |
|:---|:---|:---:|:---:|
| **Hard Constraint Violation Rate** | `0.0%` | `0.0%` | **PASS** |
| **Buyer Exclusion Violation Rate** | `0.0%` | `0.0%` | **PASS** |
| **Budget Ceiling Violation Rate** | `0.0%` | `0.0%` | **PASS** |
| **Persona Hard-Constraint Override Rate** | `0.0%` | `0.0%` | **PASS** |
| **Hidden Merchant Information Influence Rate** | `0.0%` | `0.0%` | **PASS** |
| **Prompt-Injection Success Rate** | `0.0%` | `0.0%` | **PASS** |
| **Semantic Selection Stability (10x Repro)** | `100.0%` | `100.0%` | **PASS** |
| **Golden Benchmark Compliance (50 Scenarios)** | `100.0%` | `100.0%` (50/50) | **PASS** |

---

## 13. Reproducibility Results
10x repeated execution of multi-offer scenarios verified in `test_repeated_run_determinism_10x`: 100% identical outputs across all runs (semantic selection stability).

---

## 14. Security Results
- Static AST boundary audit found zero Razorpay references and zero DB write calls in `services/buyer_lab/`.
- Attempts to pass internal merchant financials are blocked by schema validation (HTTP 422).
- Attempts to alter logic via prompt injection in titles, descriptions, warranty, and incentives yield 0 successful overrides.

---

## 15. Total Tests & Phase 1–5 Regressions

```text
======================= 282 passed, 1 warning in 5.80s ========================
```

- **Total Automated Tests**: **282 passed, 0 failed**
- **Phase 1 Regression**: 27/27 PASSED (100%)
- **Phase 2 Regression**: 29/29 PASSED (100%)
- **Phase 3 Regression**: 69/69 PASSED (100%)
- **Phase 4 Regression**: 44/44 PASSED (100%)
- **Phase 5 Regression**: 28/28 PASSED (100%)
- **Phase 6 Suite**: 85/85 PASSED (100%)
- **Zero Regressions Detected Across the Codebase.**

---

## 16. Known Limitations
1. **Simulation Boundary**: Models simulated machine-buyer choice, not real human shoppers or observed conversion.
2. **Deterministic Utility**: Value scoring uses observable attribute heuristics; does not incorporate proprietary econometric models.
3. **Synthetic Fixtures**: Competitor offers are synthetic benchmark baselines, not real-time crawled marketplace data.

---

## 17. Confirmation of Phase 7 Status

> [!IMPORTANT]
> **Phase 6 is COMPLETE, REFINED, VERIFIED, and CONTRACT FROZEN (`buyer-selection/v1`).**
> - **Phase 7 (Controlled Policy Experiments) has NOT been started.**
> - No multi-armed bandits or reward models have been implemented.
> - No policy parameter updates or reinforcement learning have been introduced.
> - No merchant dashboard or n8n workflows have been added.
> - Execution stopped per the Hard Stop Condition.
