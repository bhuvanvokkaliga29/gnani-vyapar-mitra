# Phase 6 Buyer Model: Decision Hierarchy & Persona Mechanics

## 1. Core Scientific Definitions

- **Simulated AI Buyer**: A controlled machine-buyer decision model used for offline evaluation. It is not a validated representation of real human shoppers.
- **Persona**: A bounded behavioral configuration used to vary soft-preference weighting among eligible offers. It can **never** override BuyerIntent hard constraints, exclusions, or budget limits.
- **Golden Benchmark**: A predefined set of 50 expected behavioral scenarios used to test implementation correctness, safety invariants, and boundary defenses.
- **Buyer Selection**: The selected offer under the simulation's explicit deterministic rules and inputs. It is not a prediction of actual conversion or revenue uplift.

$$\text{Golden Benchmark Compliance} \ne \text{Real-World Buyer Accuracy}$$
$$\text{Simulated Buyer Selection} \ne \text{Real Customer Conversion}$$

---

## 2. Decision Hierarchy

The AI Buyer Lab executes a strict 8-tier decision hierarchy. A lower-tier preference or persona weighting can **never override** a higher-tier constraint:

```text
1. Hard Requirements (Spec matching: laptop size, capacity, water resistance)
       ↓
2. Explicit Exclusions (Zero tolerance: materials, colors, brands)
       ↓
3. Budget Ceiling (Integer paise ceiling)
       ↓
4. Eligible Offer Set (Surviving compliant candidates)
       ↓
5. Soft Preferences (Stated preferences: warranty, delivery, accessories)
       ↓
6. Persona Weighting (Soft utility weighting among eligible offers)
       ↓
7. Buyer-Visible Value Comparison (Price efficiency, perks, delivery, warranty)
       ↓
8. Deterministic Tie-Breaks (No random choice, no merchant bias)
```

---

## 3. Hard Constraint Dominance — Mandatory Invariant

> [!IMPORTANT]
> **Persona weighting can NEVER override BuyerIntent hard constraints.**
> The persona operates exclusively on **Step 6** (soft preference weighting) over offers that have **already passed Steps 1–3**.

A persona MUST NOT:
- Modify BuyerIntent (which remains strictly immutable).
- Relax hard requirements.
- Relax explicit exclusions.
- Increase or relax the budget ceiling.
- Override eligibility or mark an ineligible offer as a winner.
- Infer unstated demographic attributes (age, gender, income, psychology).

---

## 4. Adversarial "Cheap but Invalid" Protection

In human commerce, price cuts sometimes induce shoppers to compromise on requirements. In autonomous AI-mediated commerce, machine-buyers operate under programmed user constraints.

### The Invariant
> **An offer that violates ANY hard requirement, contains an excluded attribute, or exceeds the budget CAN NEVER WIN, regardless of how cheap, heavily discounted, or bundled it is.**

### Canonical Adversarial Proof:
```text
Buyer Constraint: Requires laptop compartment >= 15.6 inches, budget <= ₹4,000.
Persona: PRICE_SENSITIVE

Candidate A (Atlas Professional Travel Pack):
- Price: ₹2,999
- Laptop Compartment: 15.6 inches
- Status: COMPLIANT

Candidate B (Budget Pack Tech - Synthetic):
- Price: ₹1,499 (50% cheaper!)
- Laptop Compartment: 14.0 inches
- Status: HARD_REQUIREMENT_VIOLATED (laptop_size)

Decision:
Candidate B is immediately filtered out.
Winner: Candidate A.
```
Even though Candidate B is 50% cheaper and the persona is `PRICE_SENSITIVE`, Candidate B is rejected before persona evaluation.

---

## 5. Behavioral Buyer Personas

Personas in Phase 6 represent **behavioral test configurations**, NOT demographic or psychological claims about human consumers.

| Persona | Behavioral Profile | Weighting Strategy |
|:---|:---|:---|
| `BALANCED` | Standard rational machine-buyer | Equal balance between preference matching and price efficiency. |
| `STRICT_REQUIREMENTS` | Conservative spec-matcher | Strict adherence to stated specifications and tolerances. |
| `PRICE_SENSITIVE` | Budget optimizer | Heavily weights price savings among compliant offers. |
| `FEATURE_PRIORITY` | Specification maximizer | Heavily weights attribute satisfaction over price savings. |
| `WARRANTY_SERVICE` | Long-term reliability buyer | Rewards extended warranties ($\ge 24$ months) and service guarantees. |
| `BUNDLE_VALUE` | Accessory-oriented buyer | Rewards included accessories, straps, and pouches. |

---

## 6. Deterministic Tie-Breaking Mechanics

When two or more offers are equally compliant and achieve identical composite value scores:
1. **Explicit Preference Count**: The offer satisfying the greatest number of explicit preferences wins.
2. **Lowest Price in Paise**: If preference counts are identical, the offer with the lower buyer-visible price in paise wins.
3. **Alphabetical `offer_id`**: If prices are identical to the exact paise, the offer with the lower alphabetical `offer_id` wins (e.g. `off_alpha` beats `off_beta`).

Random number generators and hidden merchant biases are strictly forbidden. Repeated runs over identical inputs yield identical selections 100% of the time.

---

## 7. No-Eligible-Offer Safety Rule

If every candidate offer fails hard filtering (out of stock, over budget, fails specs, or contains excluded attributes), the system **strictly refuses to select a winner**:
- `selected_offer_id`: `None`
- `selection_reasons`: `["NO_ELIGIBLE_OFFER"]`
- `selection_rationale`: Machine-buyer refused to compromise on user constraints.

The AI Buyer Lab will never "pick the least bad offer" or relax user constraints under any persona.
