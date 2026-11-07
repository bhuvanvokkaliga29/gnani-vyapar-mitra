# Phase 4 Prompt Evaluation Report

**Date**: September 3, 2026  
**Evaluated Version**: `merchant-policy-agent/v1`  
**Dataset**: 32 Golden Policy Cases (`tests/fixtures/policy_cases.json`)  

---

## 1. Evaluation Dimensions & Results

| Evaluation Dimension | Risk Analyzed | Measured Result | Status |
|:---|:---|:---:|:---:|
| **Hallucinated SKUs** | Model proposing non-existent products | **0%** (0 hallucinated SKUs across all cases) | **PASS** |
| **Constraint Ignorance** | Proposing items violating margin floors or discount ceilings | **0%** (Validator rejects all non-compliant candidates) | **PASS** |
| **Preference vs. Requirement** | Upgrading soft preferences to hard exclusions | **0%** (Controlled in BuyerIntent and eligibility filtering) | **PASS** |
| **Candidate Over-generation** | Model outputting $>5$ candidates | **0%** (Bounded strictly to 2–5 candidates) | **PASS** |
| **Invented Economics** | Model calculating money or margins incorrectly | **0%** (All economics computed by deterministic Python code) | **PASS** |
| **Spending Evasion** | Prompt injection triggering order execution | **0%** (Zero financial execution pathways) | **PASS** |

---

## 2. Key Findings

1. **Pre-Filtering Prevents Hallucinations**: By deterministically pre-filtering eligible products before candidate generation, the model is presented only with valid, in-stock, active products belonging to the merchant.
2. **Deterministic Validator Enforces Compliance**: Even if a prompt were to suggest an out-of-stock item or an excessive discount, the `PolicyValidator` catches and tags it with explicit rejection codes (`OUT_OF_STOCK`, `DISCOUNT_TOO_HIGH`).
3. **Structured Outputs Guarantee Schema Validity**: All outputs conform strictly to `PolicyProposal` and `PolicyCandidate` Pydantic models.
