# Phase 4 Deterministic Baseline & AI Strategy Coverage Comparison

**Date**: September 3, 2026  
**Evaluated Components**:
- Deterministic Baseline (`services/policy/baseline.py`)
- Merchant Policy Agent (`services/policy/agent.py`)

---

## 1. The Deterministic Baseline Heuristic

The baseline implements a pure rule-based strategy generator without AI:
1. Deterministically pre-filters active, in-stock products matching buyer category and passing hard exclusions.
2. Selects the primary matching product as a `SINGLE_PRODUCT` candidate.
3. If an explicit complementary relationship exists in merchant context, proposes a `COMPLEMENTARY_BUNDLE`.
4. Runs both through the deterministic validator and scores them against merchant objectives.
5. If neither candidate is valid, safely emits a `NO_OFFER` fallback.

---

## 2. Comparative Coverage Matrix

| Capability Dimension | Deterministic Baseline | AI Policy Agent | Comparison / Coverage |
|:---|:---:|:---:|:---|
| **Hard Constraint Safety** | 100% | 100% | Equal (both enforced by authoritative validator) |
| **Budget Enforcement** | 100% | 100% | Equal (both enforced by authoritative validator) |
| **Strategy Coverage** | Fixed (1 or 2 options) | Rich (2 to 5 options) | **Broader commercial strategy coverage** (substitutes, non-price perks, bounded discounts) |
| **Commercial Positioning** | Generic template string | Tailored value proposition | Contextual value framing grounded in attributes |
| **Tradeoff Exploration** | No substitute exploration | Proposes `ALTERNATIVE_PRODUCT` | Explores valid substitutes when primary item faces attribute tradeoffs |
| **Non-Price Incentives** | None | Proposes priority dispatch & warranty | Evaluates non-price perks that protect 100% of merchant margin |
| **Explainable Rationale** | Rigid boilerplate | Grounded context-aware reasoning | Auditable reasoning trace linked to evidence |

---

## 3. Critical Scientific Distinctions

> [!IMPORTANT]
> **Strategy Diversity $\ne$ Commercial Performance**  
> The AI Policy Agent demonstrates **broader commercial strategy coverage** than the deterministic rule-based baseline.
> This comparison proves architectural capability and strategy variety in offline evaluation. It does **NOT** prove empirical conversion uplift or financial outperformance.
> 
> **Offline Evaluation $\ne$ Observed Transaction Performance**  
> Claims of commercial performance or conversion rate increases are strictly reserved for later phases involving controlled experimentation against observed transaction outcomes (Phase 6–8).
