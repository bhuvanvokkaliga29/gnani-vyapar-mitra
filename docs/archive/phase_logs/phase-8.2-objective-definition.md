# Phase 8.2 Objective Definition: Mathematical & Economic Formulation

## 1. Primary Learning Objective

The North Star learning objective is:
> **Observed Contribution per AI Shopper**

$$\text{Observed Contribution per AI Shopper} = \frac{\sum_{i \in \text{EligibleOpportunities}} \text{ObservedContributionPaise}_i}{\text{Count}(\text{EligibleOpportunities})}$$

---

## 2. Canonical Identity System: Separation of Concepts

The system strictly distinguishes four distinct identity concepts to prevent context collapse or duplicate inflation:

1. **`opportunity_id` (`str`)**:
   - The unique decision-instance identity: `f"{experiment_id}:{scenario_id}:{variant}"`.
   - Represents the specific AI-buyer decision opportunity being evaluated.
   - Retries and duplicate webhooks match by `idempotency_key`, preventing duplicate opportunities.
2. **`buyer_context_key` (`str`)**:
   - The deterministic fingerprint describing the normalized commercial intent: `f"bck_{category}_{tier}_{digest}"`.
   - Multiple distinct opportunities can (and do) share the exact same `buyer_context_key` without collapsing.
3. **`scenario_id` (`str`)**:
   - The specific benchmark or simulation case identifier (e.g. `scen_travel_01`).
4. **`aggregation_key` (`str`)**:
   - The grouping key for policy performance retrieval: `f"{merchant_id}:{buyer_context_key}:{policy_id}:{policy_version}"`.
   - When aggregating across diverse buyer contexts in a population, `scoped_bck` is set to `"ALL_CONTEXTS"`.

---

## 3. Mathematical Contribution Formula & Economic Boundaries

Grounded strictly in Phase 2 commercial economics ([`domain/economics.py`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/domain/economics.py)):

$$\text{RealizedRevenue}_i = \text{BaselineCatalogRevenue}_i - \text{MerchantFundedDiscount}_i$$
$$\text{TotalCOGS}_i = \sum_{k \in \text{Items}} (\text{UnitCostPaise}_k \times \text{Quantity}_k)$$
$$\text{ModeledGrossContribution}_i = \text{RealizedRevenue}_i - \text{TotalCOGS}_i$$

### Strict Preservation of Negative Contribution:
If a policy offers aggressive, predatory discounts that sell products below COGS, $\text{ModeledGrossContribution}_i < 0$ is preserved as a negative integer paise. It is **never** silently clamped to zero, ensuring the learner is penalized for margin-destroying strategies.

### Authoritative Economic Boundary:
> **Boundary Notice**: This contribution formula represents **merchant modeled gross contribution** under the currently supported Phase 2 commerce model. It is **not** a complete accounting-profit calculation: overhead, corporate taxes, shipping, human labor, and unmodeled payment gateway fees (e.g. MDR) are outside the current commerce model scope and cannot enter the formula.

---

## 4. Guardrail Failure Semantics: Anti-Selection Invariant

> [!IMPORTANT]
> **Anti-Selection Bias Invariant**: A policy must NOT improve its measured economic performance merely by converting undesirable opportunities into denominator exclusions.

When an opportunity suffers a commercial guardrail failure (e.g. proposal breaches a 40% margin floor or 25% discount ceiling):
1. **Denominator Membership**: The opportunity **REMAINS in the denominator** (`is_admissible = True`).
2. **Contribution Zeroed**: Realized contribution is set to **0 paise** (`REWARD_GUARDRAIL_VIOLATION`), properly diluting the policy's contribution per shopper.
3. **Policy Disqualification**: The opportunity is flagged (`is_safety_violation = True`), incrementing `guardrail_violation_count` and forcing `is_policy_admissible = False` on the aggregate objective. This ensures no policy with safety breaches can be promoted.

### Taxonomy of Outcome Admissibility:
| Outcome Classification | Reward State | Admissible in Denominator? | Contribution |
|:---|:---|:---:|:---:|
| Converted Purchase | `REWARD_ELIGIBLE` | **YES** | Realized Rev - COGS (positive/negative) |
| Eligible Non-Purchase | `REWARD_ZERO` | **YES** | Exactly 0 paise |
| Pre-Execution Rejection | `REWARD_ZERO` | **YES** | Exactly 0 paise |
| Commercial Guardrail Failure | `REWARD_GUARDRAIL_VIOLATION` | **YES** | Exactly 0 paise (`is_policy_admissible=False`) |
| Incomplete / Insufficient Sample | `REWARD_INELIGIBLE` | **NO** (Excluded) | Excluded |
| Corrupt / Invalid Evidence | `REWARD_INVALID` | **NO** (Excluded) | Excluded |

---

## 5. Expected vs. Observed Economics Separation

$$\text{Expected Contribution (Ex Ante)} \ne \text{Observed Contribution (Ex Post)}$$

- **Expected Economics**: Derived before buyer decision and execution. Used for proposal ranking and human review.
- **Observed Economics**: Derived strictly from verified `payment.captured` webhooks and post-execution records. Only observed economics can serve as the learning objective for real transaction optimization.

---

## 6. Anti-Leakage Rules (Strict Temporal Semantics)

- **Ex Ante State (Pre-Decision)**: `BuyerIntent`, catalog prices, baseline margins, policy proposal snapshot.
- **Ex Post State (Post-Decision)**: Razorpay order ID, payment status, captured amount, realized contribution.
- Reward signals are computed strictly ex post. Post-outcome information is strictly forbidden from leaking into policy generation or buyer choice simulation.
