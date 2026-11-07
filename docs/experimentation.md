# Experimentation Engine & Policy Learning Methodology

This document defines the experimentation framework, variant structures, sample-size thresholds, and transparent decision methodology for evaluating and learning merchant policies.

---

## 1. Experimentation Framework: The Three-Variant Setup

To prove that the Merchant Policy Agent can discover commercial strategies that outperform static catalog pricing, the engine structures every experiment into three distinct treatment variants:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        TREATMENT VARIANTS                              │
├────────────────────────────────────────────────────────────────────────┤
│ CONTROL (Baseline)                                                     │
│ • Strategy: Single core SKU at static catalog list price.              │
│ • Bundle: None.                                                        │
│ • Incentive: None.                                                     │
│ • Purpose: Measures baseline organic conversion and contribution.       │
├────────────────────────────────────────────────────────────────────────┤
│ VARIANT A (Product + Accessory Cross-Sell)                             │
│ • Strategy: Core SKU + single high-affinity compatible accessory.      │
│ • Bundle: Co-packaged at individual list prices.                       │
│ • Incentive: Minimal / free accessory shipping guarantee.              │
│ • Purpose: Tests basket expansion without direct price discounting.    │
├────────────────────────────────────────────────────────────────────────┤
│ VARIANT B (Value Bundle + Targeted Incentive)                          │
│ • Strategy: Core SKU + accessory + consumable / warranty addon.        │
│ • Bundle: Bundled package price with calibrated bundle discount.       │
│ • Incentive: Explicit monetary bundle savings (within discount ceiling)│
│ • Purpose: Tests AI buyer preference for turnkey value packages.       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tracked Experimental Metrics

For each variant $v \in \{\text{CONTROL}, \text{VARIANT\_A}, \text{VARIANT\_B}\}$ across sample interactions $N_v$:

1. **Selection / Conversion Rate**:
   $$CR_v = \frac{\text{Conversions}_v}{N_v}$$
2. **Average Order Value (AOV)**:
   $$\text{AOV}_v = \frac{\text{Total Captured Revenue}_v}{\text{Conversions}_v}$$
3. **Realized Gross Margin %**:
   $$\text{Margin } \%_v = \frac{\text{Total Captured Revenue}_v - \text{Total COGS}_v}{\text{Total Captured Revenue}_v} \times 100$$
4. **Observed Revenue per Shopper (RPS)**:
   $$\text{RPS}_v = \frac{\text{Total Captured Revenue}_v}{N_v} = CR_v \times \text{AOV}_v$$
5. **Observed Contribution per Shopper (CPS)**:
   $$\text{CPS}_v = \frac{\text{Total Observed Contribution}_v}{N_v}$$

---

## 3. Transparent Decision & Learning Methodology

> [!NOTE]
> **MVP Statistical Philosophy**:
> For the MVP, we avoid black-box neural policy gradients or speculative reinforcement learning. We implement a **transparent, empirical multi-armed bandit (Epsilon-Greedy or Bayesian Thompson Sampling over Empirical Contribution)**.

### 3.1 Allocation Phases

```text
EXPLORATION PHASE (N < 30 per variant)
• Fixed equal allocation: 33.3% CONTROL | 33.3% VARIANT A | 33.3% VARIANT B
• Prevents premature convergence before observing initial variance.

EXPLOITATION / LEARNING PHASE (N ≥ 30 per variant)
• Epsilon-Greedy Allocation (ε = 0.20):
  - 80% of incoming traffic allocated to the variant with the highest observed CPS.
  - 20% distributed equally to explore alternative variants.
```

### 3.2 Decision Rules for Policy Promotion
A variant $V$ is designated as the **Recommended Winning Policy** only when:
1. **Sample Size Criterion**: $N_V \ge 30$ and $N_{\text{CONTROL}} \ge 30$.
2. **Economic Superiority**: $\text{CPS}_V > \text{CPS}_{\text{CONTROL}}$.
3. **Margin Integrity**: $\text{Margin } \%_V \ge \text{Merchant Margin Floor}$.

If $V$ yields higher conversion but lower net contribution per shopper (the "discounting trap"), the policy agent flags the variant as **economically inefficient** and prioritizes the variant maximizing net profit.

---

## 4. Statistical Integrity & Guardrails

- **No Overclaiming**: The system explicitly displays sample counts and confidence intervals. It never claims "99% statistically significant lift" when sample sizes are small ($N < 100$).
- **Stratified Persona Logging**: In the AI Buyer Lab, results are segmented by persona (`budget_sensitive`, `premium`, etc.) to demonstrate that optimal commercial policies are context-dependent rather than one-size-fits-all.
