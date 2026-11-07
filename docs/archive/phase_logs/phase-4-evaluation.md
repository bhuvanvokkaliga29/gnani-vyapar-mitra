# Phase 4 Evaluation Framework & Benchmark Results

**Date**: September 3, 2026  
**Benchmark Fixture**: `tests/fixtures/policy_cases.json` (32 Curated Cases)  
**Evaluators**: `tests/unit/test_policy_golden_suite.py`, `tests/unit/test_policy_hardening.py`, `tests/integration/test_policy_reproducibility.py`  

---

## 1. Quality & Hardening Metrics (Measured)

| Metric | Definition | Measured Value | Benchmark Target | Status |
|:---|:---|:---:|:---:|:---:|
| **Valid Candidate Rate** | `valid_candidates / generated_candidates` | **78.4%** | $>60.0\%$ | **PASS** |
| **Post-Filter Constraint Violation Rate** | Violations in approved proposals | **0.0%** | $0.0\%$ | **PASS** |
| **Mandatory NO_OFFER Fallback Compliance** | % of zero-valid-candidate situations emitting NO_OFFER | **100.0%** | $100.0\%$ | **PASS** |
| **Buyer Requirement Satisfaction** | % of approved candidates satisfying hard constraints | **100.0%** | $100.0\%$ | **PASS** |
| **Exclusion Violation Rate** | % of candidates containing forbidden attributes | **0.0%** | $0.0\%$ | **PASS** |
| **Evidence Grounding Rate** | % of candidates backed by valid structured evidence | **100.0%** | $>95.0\%$ | **PASS** |
| **Application Layer Bounding Compliance** | Requests 2–5, bounds to max 5, handles 0–1 safely | **100.0%** | $100.0\%$ | **PASS** |
| **Reproducibility Rate (5x Repeatability)** | Semantic stability across 5 repeated runs (160 runs) | **100.0%** | $100.0\%$ | **PASS** |

---

## 2. Explicit Ranking-Score Semantics

The Policy Agent computes a transparent multi-factor score:

$$\text{composite\_score} = w_1 \cdot \text{buyer\_fit} + w_2 \cdot \text{economic\_value} + w_3 \cdot \text{objective\_alignment} + w_4 \cdot \text{constraint\_safety}$$

> [!CAUTION]
> **What `composite_score` Is**:
> - An internal heuristic for **candidate prioritization and ranking** based on stated constraints and merchant goals.
> 
> **What `composite_score` Is NOT**:
> - It is **NOT** a probability of conversion.
> - It is **NOT** a purchase likelihood percentage.
> - It is **NOT** an expected revenue forecast.
> - It is **NOT** empirical causal evidence of commercial performance.
>
> The schema strictly forbids exposing `conversion_probability` or fake statistical predictions.

---

## 3. Reproducibility Semantics & Pipeline Invariants

The 5x repeated benchmark executes 160 evaluations to verify:
1. **Application-Level Determinism**: Context filtering, deterministic validation, paise arithmetic, and scoring weights execute identically on identical inputs.
2. **Contract & Schema Stability**: Output schemas, version strings (`merchant-policy/v1`), and provenance fields remain 100% byte-consistent.
3. **Semantic Stability**: Selected strategy types and product selections remain invariant.

> [!NOTE]
> In production environments with generative LLMs, natural language phrasing in rationales may exhibit stylistic variation.
> The critical system invariant is that **all model outputs are transformed into bounded, schema-valid, evidence-grounded, and deterministically validated proposals**, irrespective of text phrasing.

---

## 4. Separation of Offline Strategy Diversity vs. Commercial Performance

1. **Offline Evaluation**: Demonstrates that the Policy Agent can propose diverse, valid strategies (substitutes, non-price perks, bounded discounts) that satisfy merchant guardrails.
2. **Commercial Performance**: Real-world conversion uplift, margin optimization, and revenue growth can only be measured via empirical transaction data in Phase 6–8.
