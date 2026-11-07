# Phase 2: Deterministic Economics & Financial Formulas

This document details the exact mathematical primitives, rounding behavior, and constraint enforcement implemented in `domain/economics.py`.

---

## 1. Zero Floating-Point Arithmetic Invariant

All stored currency amounts and database columns strictly use **integer minor units** (`BIGINT` paise for INR, where ₹1.00 = 100 paise).
Floating-point numbers (`float` in Python or `REAL/FLOAT` in SQL) are strictly prohibited in financial paths to prevent binary rounding drift.

All percentage and ratio calculations use Python's arbitrary-precision `decimal.Decimal` quantized with `ROUND_HALF_UP` to 2 decimal places at the presentation boundary.

---

## 2. Mathematical Formulations

### 2.1 Gross Profit
$$\text{Gross Profit (paise)} = P - C$$
Where:
- $P$: Selling price in integer paise ($P > 0$)
- $C$: Cost of goods sold (COGS) in integer paise ($C \ge 0$)

### 2.2 Gross Margin Percentage
$$\text{Gross Margin \%} = \left( \frac{P - C}{P} \right) \times 100$$
- Evaluated via `Decimal((P - C)) / Decimal(P) * Decimal(100)`.
- Bounded and quantized: `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
- If $P \le 0$, raises `ValueError` ("Selling price must be greater than zero").

### 2.3 Physical Available Inventory
$$\text{Available to Sell} = I_{\text{total}} - I_{\text{reserved}}$$
- $I_{\text{total}} \ge 0$: Current warehouse physical quantity.
- $I_{\text{reserved}} \ge 0$: Quantity allocated to pending checkout sessions.
- Invariant: $I_{\text{reserved}} \le I_{\text{total}}$, otherwise raises `ValueError`.

### 2.4 Basket Effective Discount
For a bundle proposal with baseline list prices $p_k^{\text{base}}$ and promotional incentive $D_{\text{bundle}}$:
$$\text{Baseline Revenue} = \sum_{k=1}^{K} (p_k^{\text{base}} \times q_k)$$
$$\text{Net Basket Revenue} = \text{Baseline Revenue} - D_{\text{bundle}}$$
$$\text{Effective Discount \%} = \left( \frac{D_{\text{bundle}}}{\text{Baseline Revenue}} \right) \times 100$$

### 2.5 Basket Gross Margin
$$\text{Total COGS} = \sum_{k=1}^{K} (c_k \times q_k)$$
$$\text{Basket Gross Margin \%} = \left( \frac{\text{Net Basket Revenue} - \text{Total COGS}}{\text{Net Basket Revenue}} \right) \times 100$$

---

## 3. Strict Separation: Expected vs. Observed Contribution

Following Track 01 architectural specifications:

| Dimension | Expected Contribution ($\mathbb{E}[\text{Contribution}]$) | Observed Contribution ($\text{Contribution}_{\text{real}}$) |
| :--- | :--- | :--- |
| **Phase of Lifecycle** | Ex-Ante (During strategy generation and policy ranking) | Ex-Post (After Razorpay transaction is captured) |
| **Formula** | $P(\text{Purchase} \mid i, s) \times (\text{Net Revenue} - \text{COGS} - T_{\text{modeled}})$ | $\text{Captured Amount} - \text{Total COGS} - T_{\text{actual}}$ |
| **Source of Truth** | Deterministic catalog COGS $\times$ AI Buyer synthetic acceptance probability | Razorpay Webhook `payment.captured` event |
| **Role in Phase 2** | Foundational calculation primitives implemented in `domain/economics.py` | Transaction substrate verified in Phase 1 |
