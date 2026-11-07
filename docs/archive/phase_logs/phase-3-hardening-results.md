# Phase 3 Hardening Results Matrix

**Date**: September 3, 2026  
**Total Tests**: 125 passing / 0 failing  
**Execution Time**: 2.76s

---

## Test Distribution by Phase

| Phase | Test Count | Status |
|:---|:---|:---|
| Phase 1 — Razorpay Transaction Foundation | 27 | ✅ 27/27 |
| Phase 2 — Merchant Commerce Model | 29 | ✅ 29/29 |
| Phase 3 — Buyer Intent Engine (base) | 14 | ✅ 14/14 |
| Phase 3 — Buyer Intent Engine (hardening) | 55 | ✅ 55/55 |
| **Total** | **125** | ✅ **125/125** |

---

## Phase 3 Hardening Test Details

### Adversarial Budget Tests (13 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_rs_prefix` | `Rs 5000` → 500000 paise | ✅ |
| `test_rs_dot_prefix` | `Rs. 5,000` → 500000 paise | ✅ |
| `test_inr_prefix` | `INR 5000` → 500000 paise | ✅ |
| `test_space_k` | `5 k` → 500000 paise | ✅ |
| `test_5_5k` | `5.5k` → 550000 paise | ✅ |
| `test_one_lakh` | `₹1 lakh` → 10000000 paise | ✅ |
| `test_1_5_lakh` | `1.5 lakh` → 15000000 paise | ✅ |
| `test_up_to` | `up to ₹5k` → MAX HARD | ✅ |
| `test_no_more_than` | `no more than 5000` → MAX HARD | ✅ |
| `test_usd_currency_detection` | `USD 50` → currency=USD | ✅ |
| `test_dollar_sign` | `$50` → currency=USD | ✅ |
| `test_currency_detect_function` | INR/USD/EUR/GBP detection | ✅ |

### Adversarial Laptop Size Tests (8 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_15_6_inch` | `15.6-inch` → 15.6 | ✅ |
| `test_15_6_inches` | `15.6 inches` → 15.6 | ✅ |
| `test_14_quote` | `14"` → 14.0 | ✅ |
| `test_isolated_number_no_match` | `15 items in red` → None | ✅ |
| `test_in_preposition_no_false_match` | `15 in red` → None | ✅ |
| `test_in_preposition_stock` | `15 in stock` → None | ✅ |
| `test_legitimate_in_unit` | `15 in screen` → 15.0 | ✅ |
| `test_out_of_range_size` | `50-inch` → None | ✅ |

### Speculative Quantity Tests (6 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_definite_quantity` | `I need two` → 2 | ✅ |
| `test_speculative_might_need` | `I might need two` → None | ✅ |
| `test_speculative_maybe` | `maybe 3` → None | ✅ |
| `test_speculative_possibly` | `I possibly need two` → None | ✅ |
| `test_speculative_considering` | `considering two` → None | ✅ |
| `test_definite_buy_three` | `buy 3 units` → 3 | ✅ |

### Negation Polarity Tests (5 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_leather_is_okay` | Not an exclusion | ✅ |
| `test_red_is_fine` | Not an exclusion | ✅ |
| `test_leather_is_good` | Not an exclusion | ✅ |
| `test_no_leather_is_still_exclusion` | Correctly detected | ✅ |
| `test_not_red_is_still_exclusion` | Correctly detected | ✅ |

### Contradiction vs Correction Tests (2 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_explicit_correction_no_conflict` | "Actually make that 4000" → budget updated, no conflict | ✅ |
| `test_unexplained_budget_change_flags_conflict` | Silent budget change → conflict flagged | ✅ |

### Multi-Turn Injection Tests (2 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_injection_on_second_turn` | Turn 2 injection neutralized, Turn 1 context preserved | ✅ |
| `test_embedded_injection_in_legitimate_text` | Embedded injection neutralized, purchase extracted | ✅ |

### False Inference Defense Tests (7 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_simple_backpack_no_budget_inference` | budget=None when unstated | ✅ |
| `test_simple_backpack_no_size_inference` | No laptop_size invented | ✅ |
| `test_simple_backpack_no_color_inference` | No color preference invented | ✅ |
| `test_simple_backpack_no_material_inference` | No material preference invented | ✅ |
| `test_simple_backpack_no_quantity_inference` | quantity=None when unstated | ✅ |
| `test_simple_backpack_no_temporal_inference` | No temporal constraint invented | ✅ |
| `test_simple_backpack_no_use_case_inference` | use_case=None when unstated | ✅ |

### Schema Versioning Tests (2 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_schema_version_present` | `buyer-intent/v1` present | ✅ |
| `test_prompt_version_present` | `intent-extractor/v1` present | ✅ |

### Reproducibility Tests (3 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_all_golden_cases_reproduce_5x` | 40 cases × 5 runs = 200 executions, 100% identical | ✅ |
| `test_schema_version_stable` | `buyer-intent/v1` on all 200 runs | ✅ |
| `test_prompt_version_stable` | `intent-extractor/v1` on all 200 runs | ✅ |

### API Hardening Tests (7 tests)

| Test | Description | Status |
|:---|:---|:---|
| `test_session_a_does_not_pollute_session_b` | Complete session isolation | ✅ |
| `test_empty_message_rejected` | Empty string → 422 | ✅ |
| `test_oversized_message_rejected` | 2001 chars → 422 | ✅ |
| `test_exactly_2000_chars_accepted` | 2000 chars → 200 | ✅ |
| `test_missing_message_field_rejected` | Missing field → 422 | ✅ |
| `test_malformed_json_rejected` | Bad JSON → 422 | ✅ |
| `test_no_stack_trace_in_error_response` | No `Traceback` in response | ✅ |
| `test_single_turn_latency_under_100ms` | Processing < 100ms | ✅ |

---

## Aggregate Metrics (Post-Hardening)

| Metric | Value |
|:---|:---|
| Schema validity | 100% (40/40 golden cases) |
| Field precision | 98.1% (52/53) |
| Field recall | 98.1% (52/53) |
| False inference rate | 0.0% (verified across 7 attribute types) |
| Conflict detection | 100% (5/5 contradiction cases) |
| Reproducibility | 100% (200/200 executions) |
| Session isolation | 100% (proven via cross-session test) |
| Prompt injection defense | 100% (5 golden + 2 hardening adversarial cases) |
| Input validation | 100% (empty, oversized, malformed all rejected) |
| Processing latency | < 100ms per request |
