# Canonical Benchmark Run Report
**Contract**: `benchmark-summary/v1` | **Run ID**: `run_061156ecc33a`

## 1. Executive Summary

- **Total Scenarios Executed**: 10
- **Scenarios Passed**: 10 ✅
- **Scenarios Failed**: 0 ❌
- **Scenarios Inconclusive**: 0 ⚠️
- **Total Assertions Evaluated**: 36
- **Assertions Passed**: 36
- **Assertions Failed**: 0
- **Duration**: 4881.71 ms
- **Reproducibility Status**: `VERIFIED`

## 2. Scenario Results Breakdown

| Scenario ID | Category | Status | Assertions (Pass/Total) | Duration (ms) |
|---|---|---|---|---|
| `GOLDEN_PAYMENT_FAILURE_TRUTH` | `OUTCOME` | PASS ✅ | 9/9 | 960.20 |
| `GOLDEN_NO_OFFER_SHORT_CIRCUIT` | `DECISION` | PASS ✅ | 5/5 | 59.52 |
| `GOLDEN_SAFETY_REJECTION_BLOCK` | `SAFETY` | PASS ✅ | 3/3 | 58.10 |
| `GOLDEN_STALE_STATE_REJECTION` | `RESILIENCE` | PASS ✅ | 3/3 | 93.71 |
| `GOLDEN_DUPLICATE_OUTCOME_ONCE` | `RESILIENCE` | PASS ✅ | 3/3 | 783.73 |
| `GOLDEN_LUCKY_PURCHASE_GATE` | `LIFECYCLE` | PASS ✅ | 3/3 | 687.24 |
| `GOLDEN_LEARNING_NO_PROMOTION` | `LEARNING` | PASS ✅ | 3/3 | 735.24 |
| `GOLDEN_MERCHANT_BOUNDARY_ATTACK` | `TENANT` | PASS ✅ | 2/2 | 692.27 |
| `GOLDEN_NEGATIVE_CONTRIBUTION` | `ECONOMICS` | PASS ✅ | 2/2 | 739.98 |
| `GOLDEN_EXECUTION_FAILURE_SHIELD` | `EXECUTION` | PASS ✅ | 3/3 | 71.31 |

## 3. Failure Diagnostics

No assertion failures or infrastructure exceptions recorded.

## 4. Information Hygiene Verification

- **Secrets / Credentials Redacted**: Yes
- **Provider Auth Headers Omitted**: Yes
- **Private Merchant Unit Economics Redacted**: Yes
- **Deterministic Fields Scoped**: Yes