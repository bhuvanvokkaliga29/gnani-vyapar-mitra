# Feature Representation Schema Contract: `feature-schema/v1`

**Contract Version**: `feature-schema/v1`  
**Dimension**: 19  
**Status**: FROZEN  
**Design Principle**: **PRE-DECISION INFORMATION ONLY; ZERO POST-OUTCOME LEAKAGE**

---

## 1. Overview & Purpose

The `feature-schema/v1` contract specifies the canonical 19-dimensional feature representation used by the Merchant-Specific Contextual Linear UCB algorithm in Phase 8.4.

It converts the pair:
$$\text{Context} \times \text{Candidate Policy} \longrightarrow x \in \mathbb{R}^{19}$$

Every dimension is:
- **Finite**: Always finite float64 values; rejection of NaNs and infinities.
- **Normalized**: Bounded within $[0.0, 1.0]$ (or $[-1.0, 1.0]$).
- **Deterministic**: Identical inputs produce identical bitwise feature vectors.
- **Privacy-Safe**: Free of PII, customer IDs, and demographic profiling.
- **Pre-Decision Grounded**: Derived strictly from buyer intent and proposed policy parameters prior to execution.

---

## 2. Feature Dimension Table

| Index | Feature Name | Group | Type / Range | Grounding / Source |
|:---:|:---|:---|:---:|:---|
| **0** | `bias` | Intercept | Constant `1.0` | Global bias term |
| **1** | `budget_tier_norm` | Buyer Context | Float $[0.25, 1.0]$ | Mapped from buyer budget tier (`LOW`: 0.25, `MID`: 0.50, `HIGH`: 0.75, `PREMIUM`: 1.0) |
| **2** | `budget_amount_norm` | Buyer Context | Float $[0.0, 1.0]$ | $\min(\text{budget\_amount\_paise} / 10^6, 1.0)$ |
| **3** | `is_bulk_quantity` | Buyer Context | Binary $\{0.0, 1.0\}$ | `1.0` if requested quantity $> 1$ else `0.0` |
| **4** | `has_explicit_pref` | Buyer Context | Binary $\{0.0, 1.0\}$ | `1.0` if buyer soft preferences are specified |
| **5** | `has_hard_reqs` | Buyer Context | Binary $\{0.0, 1.0\}$ | `1.0` if buyer hard requirements are specified |
| **6** | `is_single_product` | Policy Candidate | Binary $\{0.0, 1.0\}$ | `1.0` if `StrategyType == "SINGLE_PRODUCT"` |
| **7** | `is_comp_bundle` | Policy Candidate | Binary $\{0.0, 1.0\}$ | `1.0` if `StrategyType == "COMPLEMENTARY_BUNDLE"` |
| **8** | `is_value_bundle` | Policy Candidate | Binary $\{0.0, 1.0\}$ | `1.0` if `StrategyType == "VALUE_BUNDLE"` |
| **9** | `is_alt_product` | Policy Candidate | Binary $\{0.0, 1.0\}$ | `1.0` if `StrategyType == "ALTERNATIVE_PRODUCT"` |
| **10** | `is_bounded_discount`| Policy Candidate | Binary $\{0.0, 1.0\}$ | `1.0` if `StrategyType == "BOUNDED_DISCOUNT"` |
| **11** | `is_non_price_inc` | Policy Candidate | Binary $\{0.0, 1.0\}$ | `1.0` if `StrategyType == "NON_PRICE_INCENTIVE"` |
| **12** | `discount_norm` | Policy Candidate | Float $[0.0, 1.0]$ | Proposed discount percentage / 100.0 (e.g. 15% $\to 0.15$) |
| **13** | `product_count_norm` | Policy Candidate | Float $[0.0, 1.0]$ | $\min(\text{product\_count}, 5) / 5.0$ |
| **14** | `baseline_price_norm`| Policy Candidate | Float $[0.0, 1.0]$ | $\min(\text{gross\_revenue\_paise} / 10^6, 1.0)$ |
| **15** | `budget_x_discount` | Interaction | Float $[0.0, 1.0]$ | `budget_tier_norm` $\times$ `discount_norm` |
| **16** | `pref_x_bundle` | Interaction | Float $[0.0, 1.0]$ | `has_explicit_pref` $\times$ (`is_comp_bundle` + `is_value_bundle`) |
| **17** | `budget_x_bundle` | Interaction | Float $[0.0, 1.0]$ | `budget_tier_norm` $\times$ (`is_comp_bundle` + `is_value_bundle`) |
| **18** | `price_x_discount` | Interaction | Float $[0.0, 1.0]$ | `baseline_price_norm` $\times$ `discount_norm` |

---

## 3. Anti-Leakage Audit & Guarantee

The feature vector generator [`services/learning/features.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/services/learning/features.py) enforces that **zero post-decision fields** enter the model:
- ❌ No payment success / failure status
- ❌ No captured amount
- ❌ No realized revenue or COGS
- ❌ No refund or chargeback indicators
- ❌ No conversion flags
- ❌ No downstream Razorpay transaction IDs

Any input attempting to inject post-outcome fields is rejected by Pydantic model configurations (`extra="forbid"`) and static AST boundary audits.
