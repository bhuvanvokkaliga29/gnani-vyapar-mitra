# Metrics Framework & Mathematical Definitions

This document specifies the metrics taxonomy, mathematical equations, and operational boundaries for measuring the performance of the **Merchant Policy Agent**.

---

## 1. The North-Star Metric: Expected Contribution per AI Shopper (ECPS)

The overarching objective of the Merchant Policy Agent is to maximize the expected profitable contribution generated across incoming AI buyer interactions while satisfying merchant guardrails.

As approved in Phase 0 architecture review, we strictly separate **ex-ante probabilistic expectation** from **ex-post empirical observation**.

### 1.1 Expected Contribution (Ex-Ante / Decision Time)
When formulating a candidate strategy $s$ for a given buyer intent $i$:

$$\text{Expected Contribution}(s \mid i) = P(\text{Purchase} \mid i, s) \times \mathbb{E}[\text{Contribution} \mid \text{Purchase}, s]$$

Where:
- $P(\text{Purchase} \mid i, s) \in [0, 1]$ is the estimated probability that the AI buyer selects and successfully checks out the candidate strategy $s$, conditional on intent $i$.
- $\mathbb{E}[\text{Contribution} \mid \text{Purchase}, s]$ is the expected contribution in paise if the transaction converts:
  $$\mathbb{E}[\text{Contribution} \mid \text{Purchase}, s] = \text{Proposed Basket Price} - \sum_{k \in \text{Items}} \text{COGS}_k - \text{Modeled Variable Costs}$$

### 1.2 Observed Contribution (Ex-Post / Transaction Confirmed)
When a real Razorpay transaction reaches the `captured` or `paid` state and the outcome is recorded:

$$\text{Observed Contribution} = \text{Actual Captured Amount} - \sum_{k \in \text{Delivered Items}} \text{COGS}_k - \text{Modeled Transaction Costs}$$

Where:
- $\text{Actual Captured Amount}$ is the exact currency amount returned by Razorpay Orders/Payments in paise.
- $\text{COGS}_k$ is the merchant-provided cost of goods sold for each delivered SKU $k$.
- $\text{Modeled Transaction Costs}$ represents explicit gateway fees (e.g., standard 2% payment fee) or fulfillment charges explicitly modeled in the merchant profile.

---

## 2. Supporting Commercial & Operational Metrics

### 2.1 AI Buyer Selection Rate (Conversion Rate)
$$\text{Selection Rate } (R_{\text{select}}) = \frac{\sum \mathbb{I}(\text{AI Buyer Accepts Strategy})}{\text{Total AI Buyer Intent Queries}}$$

In a live transaction setting, this represents checkout completion:
$$\text{Observed Conversion Rate } (CR) = \frac{\text{Count of Captured Orders}}{\text{Count of Evaluated Intent Interactions}}$$

### 2.2 Average Order Value (AOV)
$$\text{AOV} = \frac{\sum_{m=1}^{M} \text{Captured Order Amount}_m}{M}$$
Where $M$ is the count of successful orders. Measured in paise (or ₹).

### 2.3 Gross Margin Percentage
$$\text{Gross Margin \%} = \frac{\text{Net Revenue} - \text{COGS}}{\text{Net Revenue}} \times 100$$
The deterministic policy engine enforces that for every candidate strategy:
$$\text{Gross Margin \%} \ge \text{Merchant Margin Floor \%}$$

### 2.4 Revenue per AI Shopper (RPS)
$$\text{RPS} = \frac{\sum \text{Captured Revenue}}{\text{Total AI Shopper Interactions}} = CR \times \text{AOV}$$

### 2.5 Policy Uplift
To evaluate whether a candidate policy strategy ($V_1$) outperforms the merchant's static baseline control ($V_0$):

$$\Delta \text{ECPS} = \frac{\text{ECPS}_{V_1} - \text{ECPS}_{V_0}}{\text{ECPS}_{V_0}} \times 100\%$$

A positive uplift demonstrates that the agent is discovering commercial configurations (bundles, targeted discounts, value propositions) that win AI buyer decisions more profitably than static pricing.

---

## 3. Strict Boundary: Observed vs. Expected vs. Simulated Outcomes

To prevent misleading analytics, the system strictly isolates three tiers of financial reporting:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FINANCIAL TRUTH TIERS                           │
├────────────────────────────────────────────────────────────────────────┤
│ 1. OBSERVED REVENUE & CONTRIBUTION                                     │
│    • Origin: Verified Razorpay webhooks (order.paid / payment.captured) │
│      or API reconciliation.                                            │
│    • Status: Ground truth. Irrevocable monetary movement.              │
│    • Display: Green metric cards labeled "Verified Razorpay Revenue".  │
├────────────────────────────────────────────────────────────────────────┤
│ 2. EXPECTED VALUE (MODEL INFERENCE)                                    │
│    • Origin: Agent heuristic or regression over historical conversions.│
│    • Status: Mathematical expectation used for strategy ranking.       │
│    • Display: Purple metric cards labeled "Expected Contribution".     │
├────────────────────────────────────────────────────────────────────────┤
│ 3. SIMULATED OUTCOMES (AI BUYER LAB)                                   │
│    • Origin: Synthetic buyer personas in the controlled testbed.       │
│    • Status: Hypothesis validation and stress testing only.            │
│    • Display: Orange cards with mandatory disclaimer:                  │
│      "SYNTHETIC BENCHMARK — NOT REAL REVENUE".                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Inviolable Reporting Rule:
> **Synthetic simulation results must NEVER be aggregated with or reported as real-world transaction revenue.**
>
> All dashboard and database views must explicitly partition `is_simulated = TRUE` from verified Razorpay production/test-mode financial events.
