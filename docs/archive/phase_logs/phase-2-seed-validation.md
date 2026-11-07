# Phase 2 Seed Data Validation & Economic Proof

This document provides independent mathematical validation of the seed catalog for **Atlas Travel Gear** (`merch_atlas_travel`), comparing manual hand-calculations against system outputs.

---

## 1. Catalog Unit Economics Audit

| Product SKU | Selling Price ($P$) | Unit COGS ($C$) | Gross Profit ($P - C$) | Manual Gross Margin % | System Computed Margin % | Stock Status | Eligibility |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `SKU-BACKPACK-01` | ₹2,999.00 (`299900` p) | ₹1,800.00 (`180000` p) | ₹1,199.00 (`119900` p) | $\frac{1199}{2999} = 39.9799...\% \to \mathbf{39.98\%}$ | `39.98%` | 30 in stock | `Eligible` (Margin $\ge 25\%$) |
| `SKU-SLEEVE-02` | ₹799.00 (`79900` p) | ₹350.00 (`35000` p) | ₹449.00 (`44900` p) | $\frac{449}{799} = 56.1952...\% \to \mathbf{56.20\%}$ | `56.20%` | 50 in stock | `Eligible` (Margin $\ge 25\%$) |
| `SKU-MOUSE-03` | ₹999.00 (`99900` p) | ₹500.00 (`50000` p) | ₹499.00 (`49900` p) | $\frac{499}{999} = 49.9499...\% \to \mathbf{49.95\%}$ | `49.95%` | 40 in stock | `Eligible` (Margin $\ge 25\%$) |
| `SKU-HUB-04` | ₹1,499.00 (`149900` p) | ₹700.00 (`70000` p) | ₹799.00 (`79900` p) | $\frac{799}{1499} = 53.3022...\% \to \mathbf{53.30\%}$ | `53.30%` | 25 in stock | `Eligible` (Margin $\ge 25\%$) |
| `SKU-BACKPACK-PRO` | ₹4,999.00 (`499900` p) | ₹2,800.00 (`280000` p) | ₹2,199.00 (`219900` p) | $\frac{2199}{4999} = 43.9887...\% \to \mathbf{43.99\%}$ | `43.99%` | 15 in stock | `Eligible` (Margin $\ge 25\%$) |

All manual calculations match the system's Decimal `ROUND_HALF_UP` calculations to the exact hundredth of a percent.

---

## 2. Sample Commercial Basket Manual Verification

Let us construct a proposed AI Buyer travel bundle:
- **Item 1**: `prod_travel_backpack` (Qty: 1, Price: ₹2,999, COGS: ₹1,800)
- **Item 2**: `prod_laptop_sleeve` (Qty: 1, Price: ₹799, COGS: ₹350)
- **Promotional Bundle Discount**: ₹189.90 (`18990` paise) — exactly 5% of combined baseline price.

### Manual Hand Calculations:
1. **Baseline Catalog Revenue**:
   $$\text{Baseline} = 299900 + 79900 = 379800\text{ paise (₹3,798.00)}$$
2. **Effective Promotional Discount**:
   $$\text{Discount \%} = \frac{18990}{379800} \times 100 = 5.00\%$$
   - **Guardrail Check**: $5.00\% \le 8.00\%$ (Maximum discount ceiling) $\implies$ **PASS**
3. **Net Basket Revenue**:
   $$\text{Net Revenue} = 379800 - 18990 = 360810\text{ paise (₹3,608.10)}$$
4. **Total COGS**:
   $$\text{Total COGS} = 180000 + 35000 = 215000\text{ paise (₹2,150.00)}$$
5. **Gross Profit**:
   $$\text{Gross Profit} = 360810 - 215000 = 145810\text{ paise (₹1,458.10)}$$
6. **Basket Gross Margin %**:
   $$\text{Margin \%} = \frac{145810}{360810} \times 100 = 40.41185...\% \to \mathbf{40.41\%}$$
   - **Guardrail Check**: $40.41\% \ge 25.00\%$ (Minimum margin floor) $\implies$ **PASS**

### Automated System Output (`evaluate_basket_economics`):
- `gross_revenue_paise`: `360810`
- `total_cogs_paise`: `215000`
- `gross_profit_paise`: `145810`
- `gross_margin_percent`: `Decimal("40.41")`
- `effective_discount_percent`: `Decimal("5.00")`
- `is_compliant`: `True`
- `violation_reasons`: `[]`

**Parity**: 100% exact mathematical match down to the exact integer paise and hundredth of a percent.
