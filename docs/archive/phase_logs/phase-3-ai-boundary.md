# Phase 3 AI Boundary Specification

**Date**: September 3, 2026  
**Contract Version**: `buyer-intent/v1`

---

## Overview

The Phase 3 Buyer Intent Engine draws a strict line between **deterministic code** (no AI, no LLM) and **semantic understanding** tasks. This document defines that boundary.

## Deterministic Code (No AI/LLM)

The following tasks are performed entirely by hand-authored regex patterns, string matching, and arithmetic — with zero LLM inference:

| Task | Module | Technique |
|:---|:---|:---|
| Currency parsing (₹, Rs, INR, $, USD, EUR, GBP) | `normalizer.py` → `parse_raw_amount_to_paise()` | Regex + `int(float())` |
| Paise conversion (rupees × 100) | `normalizer.py` → `parse_raw_amount_to_paise()` | Integer arithmetic |
| Budget type classification (MAX, RANGE, APPROXIMATE, TARGET) | `normalizer.py` → `extract_budget()` | Ordered regex cascade |
| Lakh/K shorthand expansion | `normalizer.py` → `parse_raw_amount_to_paise()` | Regex + multiplier |
| Laptop size extraction (15.6-inch, 16", etc.) | `normalizer.py` → `extract_laptop_size()` | Regex with unit validation |
| Quantity extraction with speculativeness check | `normalizer.py` → `extract_quantity()` | Marker word filter + regex |
| Exclusion extraction (no leather, not red) | `normalizer.py` → `extract_exclusions()` | Negative pattern regex |
| Positive affirmation detection (leather is okay) | `normalizer.py` → `_is_positive_affirmation()` | Substring match |
| Category classification | `normalizer.py` → `extract_category_and_use_case()` | Keyword cascade |
| Use case extraction | `normalizer.py` → `extract_category_and_use_case()` | Keyword cascade |
| Temporal constraint extraction | `normalizer.py` → `extract_temporal()` | Day-name regex |
| Budget validation (min ≤ max, strictly positive) | `validator.py` → `validate_and_enrich_intent()` | Arithmetic comparison |
| Contradiction detection (pref ↔ exclusion collision) | `validator.py` → `validate_and_enrich_intent()` | Set intersection |
| Unknowns enumeration | `validator.py` → `validate_and_enrich_intent()` | Presence check |
| Confidence calibration | `validator.py` → `validate_and_enrich_intent()` | Rule-based scoring |
| Prompt injection detection & neutralization | `extractor.py` → `sanitize_and_check_injection()` | Regex pattern matching |
| Multi-turn intent merging | `conversation.py` → `merge_intents()` | Field-by-field merge logic |
| Correction vs contradiction distinction | `conversation.py` → `merge_intents()` | Correction marker detection |
| Currency detection | `normalizer.py` → `detect_currency()` | Regex pattern matching |

## Semantic Understanding Tasks (Reserved for Future LLM)

The following tasks are **NOT currently implemented** and would require LLM inference if added in future phases:

| Task | Status | Notes |
|:---|:---|:---|
| Free-form product description understanding | Not implemented | Would require NLU |
| Ambiguous category resolution ("something for my trip") | Partial (keyword-based) | Deeper understanding would need LLM |
| Sarcasm/irony detection | Not implemented | Would need pragmatic inference |
| Cross-lingual intent parsing | Not implemented | Would need multilingual model |
| Complex temporal reasoning ("before my anniversary") | Not implemented | Would need world knowledge |

## Current Architecture: Zero LLM Calls

The v1 Buyer Intent Engine makes **zero LLM API calls**. All extraction is deterministic regex + string matching. This guarantees:

1. **Zero latency variance** — No network round-trip to an LLM endpoint
2. **Zero cost** — No per-token inference charges
3. **Zero hallucination risk** — Cannot invent facts
4. **Perfect reproducibility** — Same input → same output, always
5. **Offline operation** — Works without internet connectivity

## Boundary Contract

```
┌────────────────────────────────────────────────────┐
│                 DETERMINISTIC ZONE                  │
│  normalizer.py, validator.py, extractor.py,         │
│  conversation.py                                    │
│                                                     │
│  Input: raw text string                             │
│  Output: BuyerIntent (Pydantic model)               │
│  Guarantees: zero hallucination, deterministic,      │
│              reproducible, < 1ms latency             │
├────────────────────────────────────────────────────┤
│                    BOUNDARY                          │
│  BuyerIntent v1 schema (frozen)                     │
│  MerchantCommerceContext (frozen from Phase 2)      │
├────────────────────────────────────────────────────┤
│              FUTURE AI ZONE (Phase 4+)              │
│  Policy Agent: BuyerIntent × Commerce → Decisions   │
│  LLM-powered reasoning, product selection, ranking  │
│  pricing optimization, offer generation              │
└────────────────────────────────────────────────────┘
```
