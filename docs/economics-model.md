# Merchant Economic Model & Deterministic Constraints

This document defines the formal mathematical models governing merchant revenue, unit costs, gross margins, contribution calculations, and hard deterministic guardrails.

---

## 1. Core Economic Formulations

All internal monetary calculations are conducted in **integer paise** ($\text{₹}1.00 = 100 \text{ paise}$) to prevent floating-point arithmetic errors.

### 1.1 Gross Revenue
For a commercial basket consisting of items $k \in \{1, \dots, K\}$ with unit proposed price $p_k$ and quantity $q_k$, less any bundle-level promotional incentive $D_{\text{bundle}}$:

$$\text{Gross Basket Revenue} = \sum_{k=1}^{K} (p_k \times q_k) - D_{\text{bundle}}$$

Subject to: $\text{Gross Basket Revenue} > 0$.

### 1.2 Cost of Goods Sold (COGS)
Merchant-provided product cost sheet defines $c_k$ (unit procurement or manufacturing cost for SKU $k$):

$$\text{Total COGS} = \sum_{k=1}^{K} (c_k \times q_k)$$

### 1.3 Gross Margin Percentage
$$\text{Gross Margin \%} = \frac{\text{Gross Basket Revenue} - \text{Total COGS}}{\text{Gross Basket Revenue}} \times 100$$

### 1.4 Modeled Transaction Costs
In the MVP, transaction processing costs $T$ are explicitly modeled based on standard payment fees (e.g., standard domestic card/UPI MDR fee of 2.0%):

$$T = \lfloor \text{Gross Basket Revenue} \times \text{MDR Rate} \rfloor$$

---

## 2. Separated Contribution Formulations

Following architectural review, we strictly separate **Expected Contribution** (used for strategy ranking and optimization) from **Observed Contribution** (derived from confirmed transactions).

### 2.1 Expected Contribution (Ex-Ante / Strategy Planning)
When evaluating a proposed candidate strategy $s$ against buyer intent $i$:

$$\text{Expected Contribution}(s \mid i) = P(\text{Purchase} \mid i, s) \times \mathbb{E}[\text{Contribution} \mid \text{Purchase}, s]$$

Where:
- $P(\text{Purchase} \mid i, s)$ is the estimated purchase probability for strategy $s$ under intent $i$.
- $\mathbb{E}[\text{Contribution} \mid \text{Purchase}, s] = \text{Gross Basket Revenue}(s) - \text{Total COGS}(s) - T(s)$.

### 2.2 Observed Contribution (Ex-Post / Transaction Confirmed)
When a Razorpay order is confirmed via webhook or API reconciliation:

$$\text{Observed Contribution} = \text{Captured Amount} - \sum_{k \in \text{Delivered Items}} (c_k \times q_k) - T_{\text{actual}}$$

---

## 3. Deterministic Business Guardrails

Every candidate strategy proposed by an LLM must pass five deterministic validation gates before an order can be created:

### Gate 1: Margin Floor Constraint
The gross margin percentage of the proposed basket must meet or exceed the merchant's configured margin floor $M_{\text{floor}}$:

$$\text{Gross Margin \%} \ge M_{\text{floor}}$$

*Action on failure*: Immediate rejection with error code `ERR_MARGIN_FLOOR_VIOLATION`.

### Gate 2: Maximum Discount Ceiling
The effective discount offered across the basket relative to baseline catalog list prices $p_k^{\text{base}}$ must not exceed the ceiling $D_{\text{max}}$:

$$\text{Effective Discount \%} = \frac{\sum (p_k^{\text{base}} \times q_k) - \text{Gross Basket Revenue}}{\sum (p_k^{\text{base}} \times q_k)} \times 100 \le D_{\text{max}}$$

*Action on failure*: Immediate rejection with error code `ERR_DISCOUNT_CEILING_EXCEEDED`.

### Gate 3: Buyer Budget Ceiling
The gross basket revenue must not exceed the maximum budget declared in the buyer intent $B_{\text{buyer}}$:

$$\text{Gross Basket Revenue} \le B_{\text{buyer}}$$

*Action on failure*: Immediate rejection with error code `ERR_BUDGET_EXCEEDED`.

### Gate 4: Real-Time Inventory Availability
For every item $k$ in the proposal, the requested quantity $q_k$ must not exceed current physical stock $I_k$:

$$q_k \le I_k \quad \forall k \in \{1, \dots, K\}$$

*Action on failure*: Immediate rejection with error code `ERR_INSUFFICIENT_INVENTORY`.

### Gate 5: Merchant Priority SKU Preference
If the merchant designates priority inventory clearance categories, the policy agent scores candidate bundles higher when they include valid priority SKUs, provided Gates 1–4 are fully satisfied.
