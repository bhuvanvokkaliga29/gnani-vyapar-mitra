# Phase 2: Seed Catalog Specification — Atlas Travel Gear

This document records the exact catalog, economics, inventory, and affinity relationships seeded for demo merchant **Atlas Travel Gear** (`merch_atlas_travel`).

---

## 1. Merchant Profile

- **Merchant ID**: `merch_atlas_travel`
- **Merchant Name**: Atlas Travel Gear
- **Currency**: `INR`
- **Business Objective**: `BALANCE_REVENUE_AND_MARGIN`
- **Financial Guardrails**:
  - Minimum Gross Margin Floor: `25.00%`
  - Maximum Promotional Discount Ceiling: `8.00%`
  - Target AOV: ₹4,000.00 (`400000` paise)

---

## 2. Product Catalog & Unit Economics

All monetary values are stored in **integer paise** (₹1.00 = 100 paise).

| SKU | Product Name | Category | Retail Price (Paise) | Retail Price (INR) | Unit COGS (Paise) | Gross Profit (INR) | Gross Margin % | Physical Stock |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `SKU-BACKPACK-01` | Atlas All-Weather Travel Backpack (35L) | Bags & Luggage | 299900 | ₹2,999.00 | 180000 | ₹1,199.00 | 39.98% | 30 |
| `SKU-SLEEVE-02` | Shock-Resistant 16-Inch Laptop Sleeve | Electronics Accessories | 79900 | ₹799.00 | 35000 | ₹449.00 | 56.20% | 50 |
| `SKU-MOUSE-03` | Ergonomic Multi-Device Bluetooth Mouse | Computer Peripherals | 99900 | ₹999.00 | 50000 | ₹499.00 | 49.95% | 40 |
| `SKU-HUB-04` | 7-in-1 Aluminum USB-C Travel Hub | Computer Peripherals | 149900 | ₹1,499.00 | 70000 | ₹799.00 | 53.30% | 25 |
| `SKU-BACKPACK-PRO` | Atlas Executive Ballistic Nylon Pack (42L) | Bags & Luggage | 499900 | ₹4,999.00 | 280000 | ₹2,199.00 | 43.99% | 15 |

---

## 3. Product Affinity Relationships

Relationships are explicitly scoped to `merch_atlas_travel` and prevent invalid cross-merchant links.

| Primary Product | Related Product | Relationship Type | Affinity Score | Source |
| :--- | :--- | :--- | :---: | :--- |
| `prod_travel_backpack` | `prod_laptop_sleeve` | `COMPLEMENTARY` | 0.85 | `merchant_defined` |
| `prod_travel_backpack` | `prod_premium_backpack` | `SUBSTITUTE` | 0.70 | `merchant_defined` |
| `prod_laptop_sleeve` | `prod_travel_backpack` | `BUNDLE_COMPONENT` | 0.90 | `merchant_defined` |
| `prod_wireless_mouse` | `prod_usbc_hub` | `COMPLEMENTARY` | 0.75 | `merchant_defined` |
| `prod_travel_backpack` | `prod_premium_backpack` | `UPSELL` | 0.65 | `merchant_defined` |

---

## 4. Merchant Catalog Priorities

- **Priority Focus SKUs**: `["prod_travel_backpack", "prod_laptop_sleeve"]`
- **Priority Focus Categories**: `["Bags & Luggage"]`
- **Clearance Inventory Targets**: `["prod_wireless_mouse"]`
