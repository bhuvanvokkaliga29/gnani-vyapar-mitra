# Phase 8.2 Adversarial Review: 29 Targeted Evaluation Cases

The Phase 8.2 Reward and Objective Layer was subjected to a comprehensive semantic audit and adversarial verification across 29 distinct scenarios spanning guardrails, revenue semantics, identity integrity, aggregation rules, and versioning.

All 29 cases pass deterministically in [`tests/integration/test_reward_adversarial.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/tests/integration/test_reward_adversarial.py).

---

## Adversarial Evaluation Matrix

### Guardrail Cases
| # | Case | Test Description | Deterministic System Behavior |
|:---:|:---|:---|:---|
| **1** | Guardrail-safe successful purchase | Policy outcome satisfies all margin floors and discount ceilings. | `REWARD_ELIGIBLE`, contribution calculated, admissible in denominator. |
| **2** | Guardrail-safe non-purchase | Policy outcome satisfies guardrails, but buyer rejected offer. | `REWARD_ZERO`, contribution = 0, admissible in denominator. |
| **3** | Guardrail violation before execution | Phase 5 Execution Gate rejects offer due to margin floor. | `REWARD_ZERO`, contribution = 0, admissible in denominator. |
| **4** | Unexpected guardrail failure | Post-hoc experiment observation records margin floor violation. | `REWARD_GUARDRAIL_VIOLATION`, contribution = 0, `is_safety_violation=True`. |
| **5** | High-revenue but unsafe outcome | High revenue variant breaching margin constraints. | High revenue ignored; contribution set to 0; policy flagged inadmissible. |
| **6** | Unsafe outcome cannot artificially improve objective | 20 guardrail failures mixed with 80 compliant outcomes. | 20 failures stay in denominator (diluting average from ₹100 to ₹80) + `is_policy_admissible=False`. |

### Revenue Cases
| # | Case | Test Description | Deterministic System Behavior |
|:---:|:---|:---|:---|
| **7** | Catalog revenue equals executed revenue | No promotional discount applied. | `realized_revenue_paise == baseline_catalog_price_paise`. |
| **8** | Proposed price differs from executed amount | Execution recalculation updates dynamic inventory price. | Phase 5 authorized amount is authoritative; reward reflects actual captured revenue. |
| **9** | Discount calculation | Baseline catalog price minus merchant-funded discount. | Exact formula: `RealizedRevenue = BaselineCatalogRevenue - MerchantFundedDiscount`. |
| **10** | Payment failure | Razorpay test-mode payment failed or abandoned. | `REWARD_ZERO`, contribution = 0 paise, retained in denominator. |
| **11** | Captured payment | Webhook `payment.captured` verified. | `REWARD_ELIGIBLE`, contribution = `captured_amount - COGS`. |
| **12** | Missing authoritative revenue input | Corrupt evidence record with missing revenue figures. | Flagged as `REWARD_INVALID` and excluded from objective population. |
| **13** | Unsupported accounting-cost field | Attempting to inject taxes, overhead, or gateway fees. | Schema validation rejects unauthorized fields via `extra="forbid"`. |

### Identity Cases
| # | Case | Test Description | Deterministic System Behavior |
|:---:|:---|:---|:---|
| **14** | Same buyer context, two distinct opportunities | Two separate shoppers with identical category and budget. | Unique `opportunity_id`s preserved; both counted in denominator. |
| **15** | Same opportunity, duplicate observation | Webhook replayed or observation duplicated. | Deduplicated via `idempotency_key`; exactly one reward generated. |
| **16** | Retry for same opportunity | System retries evaluation for a scenario. | Attributed to same `opportunity_id`, preserving single-opportunity count. |
| **17** | Different policies, same buyer context | Control and Treatment evaluated under same intent. | Strict policy attribution enforced; cross-policy aggregation rejected. |
| **18** | Same policy, different opportunities | Policy evaluated across multiple scenarios. | Aggregated across all distinct `opportunity_id`s; denominator is scenario count. |
| **19** | Cross-merchant identity collision | Evidence from Merchant A and Merchant B mixed. | Raises `RewardAttributionError`, enforcing strict multi-tenant isolation. |
| **20** | Experiment/variant attribution | Deterministic mapping between experiment, variant, and policy. | Provenance linkage verified on every reward record. |

### Aggregation Cases
| # | Case | Test Description | Deterministic System Behavior |
|:---:|:---|:---|:---|
| **21** | Zero successful purchases | 10 opportunities all resulted in `NO_SELECTION`. | Total contribution = 0, denominator = 10, objective = 0 paise per shopper. |
| **22** | One success + many non-purchases | 1 success (₹1,000) + 9 non-purchases (₹0). | Correctly diluted over all 10 opportunities: objective = ₹100/shopper, NOT ₹1,000. |
| **23** | Eligible + ineligible observations | Valid opportunities mixed with corrupt evidence. | Ineligible excluded from denominator; valid retained. |
| **24** | Safety failure mixed with normal outcomes | Guardrail failures present in aggregation. | Failures stay in denominator with 0 contribution; `is_policy_admissible = False`. |
| **25** | Duplicate evidence mixed with valid evidence | Replay events mixed in dataset. | Idempotency guarantees each opportunity counted exactly once. |

### Regression & Versioning
| # | Case | Test Description | Deterministic System Behavior |
|:---:|:---|:---|:---|
| **26** | Existing reward-version behavior remains stable | Contract stability for `merchant-reward/v1`. | All existing consumers and routers function with zero regression. |
| **27** | Contribution-formula version remains explicit | Explicit formula provenance `contribution-formula/v1`. | Recorded on every reward and objective record. |
| **28** | Historical reward results remain interpretable | Immutability and auditability preserved. | Stored rewards remain self-contained with complete provenance. |
| **29** | Full existing test suite remains green | Complete regression across all phases (1 to 8.2). | 421/421 tests passing (100% pass rate). |
