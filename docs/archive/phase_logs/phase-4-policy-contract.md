# Phase 4 Policy Proposal Contract Specification

**Contract Version**: `merchant-policy/v1`  
**Prompt Version**: `merchant-policy-agent/v1`  
**Date**: September 3, 2026  
**Status**: APPROVED & FROZEN  

---

## 1. Overview

This document specifies the strict, machine-readable contract emitted by the **Merchant Policy Agent**. The output of Phase 4 is a `PolicyProposal` that pairs proposed candidate commercial strategies with exact deterministic economic evaluations, transparent ranking scores, and machine-readable validation verdicts.

---

## 2. The Core Schema: `PolicyProposal`

```python
class PolicyProposal(BaseModel):
    proposal_id: str                      # Unique identifier (e.g. prop_a1b2c3d4e5f6)
    buyer_intent_id: Optional[str]        # Correlated buyer intent ID
    merchant_id: str                      # Tenant merchant identifier
    policy_version: str                   # "merchant-policy/v1"
    prompt_version: str                   # "merchant-policy-agent/v1"
    intent_version: str                   # "buyer-intent/v1"
    context_version: str                  # "commerce-context/v1"
    validator_version: str                # "deterministic-validator/v1"
    objective: str                        # Merchant commercial objective (e.g. BALANCE_REVENUE_AND_MARGIN)
    model_provider: str                   # Model provider name
    model_name: str                       # Model identifier
    status: ProposalStatus                # Overall proposal status
    candidates: List[PolicyCandidate]     # Bounded list of 2–5 evaluated candidates
    selected_candidate: Optional[PolicyCandidate] # Top-ranked compliant candidate (or NO_OFFER fallback)
    total_candidates: int                 # Count of generated candidates
    valid_candidates_count: int           # Count of compliant approved candidates
    rejected_candidates_count: int        # Count of rejected candidates
    is_provisional: bool                  # True (proposal is advisory, based on generation snapshot)
    context_snapshot_at: datetime         # Timestamp of context snapshot used for decision
    generation_timestamp: datetime        # Exact generation timestamp
    audit_trail: Dict[str, Any]           # Full audit execution trace
    created_at: datetime                  # Generation timestamp
```

### Candidate Bounding Architecture

```text
LLM generation target: 2–5 candidates
                ↓
Application sanitization: 0–5 candidates (hard-bounds to maximum of 5, handles 0–1 safely)
                ↓
Deterministic validation
                ↓
0 valid candidates survive
                ↓
Mandatory NO_OFFER fallback
```

> **Bounding Guarantee**: The system requests 2–5 candidates, while the application layer hard-bounds the received candidate list to a maximum of 5 and safely handles 0–1 candidates.

### Context Snapshot Semantics & Advisory Status

> [!IMPORTANT]
> **A Phase 4 proposal is advisory and provisional (`is_provisional = True`).**
> It represents a commercial strategy recommendation based on the **context snapshot available at generation time**.
> It is **NOT** a guaranteed executable transaction. Before any financial execution in Phase 5, the proposal must be revalidated against fresh deterministic merchant state (live stock and fresh pricing).

### Mandatory `NO_OFFER` Fallback

When all generated candidates violate deterministic guardrails (budget, margin floor, out-of-stock, exclusions, or invalid relationships):
1. The agent **NEVER** selects an invalid candidate.
2. The agent automatically emits a compliant `NO_OFFER` strategy with `rejection_reasons` summarizing all guardrail failures.
3. Proposal status is set to `VALID` (with `selected_candidate.strategy_type == NO_OFFER`).

### Proposal Status Transitions: 3-Tier Semantic Freeze

| Status | Exact Semantic Meaning | Downstream Action |
|:---|:---|:---|
| `VALID` | Proposal passed Phase 4 deterministic validation (or valid `NO_OFFER` fallback) | Merchant reviewable / safe termination |
| `APPROVED_FOR_EVALUATION` | Proposal passed Phase 4 validation and is eligible to be evaluated in a future experiment (Phase 6–8) | Forward top candidate to Phase 5 Execution Gate |
| `REJECTED` | Unhandled candidate validation rejection without fallback | Log rejection, trigger safe fallback |
| `CLARIFICATION_REQUIRED` | BuyerIntent had unresolved conflicts or missing critical dimensions | Request buyer clarification before proposing offers |

> [!CAUTION]
> **Execution Status Isolation**:
> `EXECUTION_APPROVED` is strictly reserved for Phase 5+ Deterministic Commercial Execution Gate revalidation against real-time database state.
> It is **strictly forbidden** in Phase 4. `APPROVED_FOR_EVALUATION` means *eligible for experimental evaluation*, NOT *approved for financial execution*.

> [!NOTE]
> The PolicyProposal contains **NO `EXECUTED` status**. Execution is explicitly separated into Phase 5.

---

## 3. Candidate Strategy: `PolicyCandidate`

```python
class PolicyCandidate(BaseModel):
    candidate_id: str                          # Unique candidate identifier
    strategy_type: StrategyType                # Taxonomy classification
    product_ids: List[str]                     # Included catalog product IDs
    bundle_components: List[Dict[str, Any]]    # Component breakdown with quantities
    incentive: Optional[IncentiveProposal]     # Proposed promotional discount or non-price perk
    positioning: Optional[str]                 # Value proposition framing
    rationale: str                             # Grounded explanation
    confidence: ConfidenceLevel                # HIGH, MEDIUM, LOW
    evidence: List[PolicyEvidence]             # Audit traces to structured facts
    deterministic_economics: Optional[CandidateEconomics] # Computed financial figures
    validation_status: CandidateValidationStatus # APPROVED or REJECTED
    rejection_reasons: List[str]               # Explicit machine-readable codes
    score: Optional[PolicyScore]               # Transparent multi-factor score
```

---

## 4. Strategy Taxonomy

The Policy Agent is restricted to 7 controlled strategy types:

| Strategy Type | Description | Required Grounding |
|:---|:---|:---|
| `SINGLE_PRODUCT` | Single best-fit catalog product | Matches buyer category and core requirements |
| `COMPLEMENTARY_BUNDLE` | Primary product paired with a complementary item | Explicit `COMPLEMENTARY` relationship in context |
| `VALUE_BUNDLE` | High-utility combination of related items | Explicit `BUNDLE_COMPONENT` relationship |
| `ALTERNATIVE_PRODUCT` | Substitute product with different attribute tradeoffs | Explicit `SUBSTITUTE` relationship or catalog sibling |
| `NON_PRICE_INCENTIVE` | Product offered with non-monetary perk (shipping, warranty) | Merchant margin protection |
| `BOUNDED_DISCOUNT` | Product offered with a bounded discount percentage | Discount $\le$ merchant discount ceiling |
| `NO_OFFER` | No commercial offer proposed | Budget impossible or all items out of stock |

---

## 5. Rejection Taxonomy

Every candidate rejected by the deterministic validator is tagged with explicit machine-readable reasons:

| Rejection Code | Trigger Condition |
|:---|:---|
| `MARGIN_TOO_LOW` | Basket gross margin % $<$ merchant `minimum_margin_percent` |
| `DISCOUNT_TOO_HIGH` | Proposed discount % $>$ merchant `maximum_discount_percent` |
| `OVER_BUDGET` | Net basket revenue paise $>$ buyer `max_amount_paise` |
| `OUT_OF_STOCK` | Requested quantity $>$ product `available_to_sell` |
| `EXCLUDED_BY_BUYER` | Product contains material, color, or property forbidden in `BuyerIntent.exclusions` |
| `INACTIVE_PRODUCT` | Product `is_active == False` |
| `INVALID_RELATIONSHIP` | Bundled items have no explicit relationship in `MerchantCommerceContext` |
| `UNKNOWN_PRODUCT` | Proposed SKU does not exist in merchant catalog |
| `CROSS_MERCHANT_PRODUCT` | Product belongs to a different merchant tenant |
| `REQUIREMENT_NOT_MET` | Primary product fails hard buyer requirement (e.g. laptop size) |
| `ZERO_ITEMS` | Candidate contains empty product list for non-NO_OFFER strategy |

---

## 6. Deterministic Economics: `CandidateEconomics`

Financial values are strictly computed by deterministic Python code using integer paise and exact `Decimal` percentages:

```python
class CandidateEconomics(BaseModel):
    gross_revenue_paise: int              # Sum of regular unit prices * quantity
    promotional_discount_paise: int       # Exact paise discount
    net_revenue_paise: int                # Customer payable amount before execution
    total_cogs_paise: int                 # Sum of unit costs * quantity
    gross_profit_paise: int               # net_revenue - total_cogs
    gross_margin_percent: Decimal         # ((net_revenue - cogs) / net_revenue) * 100
    effective_discount_percent: Decimal   # (discount / gross_revenue) * 100
    is_compliant: bool                    # Margin >= floor AND discount <= ceiling
```

---

## 7. Transparent Scoring: `PolicyScore`

```python
class PolicyScore(BaseModel):
    buyer_fit_score: float                # Fit to stated preferences and use cases (0.0–1.0)
    economic_value_score: float           # Contribution toward merchant target AOV (0.0–1.0)
    objective_alignment_score: float      # Alignment with active merchant objective (0.0–1.0)
    constraint_safety_score: float        # Safety buffer above guardrail floors (0.0–1.0)
    composite_score: float                # Objective-weighted composite ranking score (0.0–1.0)
```

No fake conversion probabilities are emitted. Scores reflect grounded structural alignment.
