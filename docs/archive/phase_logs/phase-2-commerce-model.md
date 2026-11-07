# Phase 2: Merchant Commerce Model Architecture

This document describes the architectural design, relational models, and invariants governing the merchant commercial knowledge layer in **Phase 2**.

---

## 1. Architectural Purpose & Separation of Concerns

The fundamental rule of Phase 2 is:
> **The Merchant Commerce Model is the inviolable deterministic source of truth.**

LLMs and policy agents must **never** become the source of truth for:
- Retail selling prices
- Unit COGS or gross margins
- Physical inventory stock counts
- Merchant financial constraints (margin floors, discount ceilings, target AOV)
- Product affinity or compatibility relationships

The future Policy Agent acts as a reasoning engine over this substrate; it cannot invent, modify, or hallucinate commercial parameters.

```text
                  Merchant
                     │
                     ▼
             Commerce Model
                     │
       ┌─────────────┼─────────────┐
       │             │             │
       ▼             ▼             ▼
    Catalog       Economics     Constraints
       │             │             │
       └─────────────┼─────────────┘
                     ▼
          Merchant Commerce Context
                     │
                     ▼
         Future Policy Agent (Phase 3+)
```

---

## 2. Core Domain Entities

### 2.1 `Merchant`
- **Tenant Scope**: Encapsulates merchant identity, base currency, status, optimization objective, and financial guardrails.
- **Key Invariants**:
  - `minimum_margin_percent`: Non-negative decimal floor (default: `25.00%`).
  - `maximum_discount_percent`: Bounded decimal ceiling (default: `8.00%`).
  - `target_aov_paise`: Integer minor units (default: `400000` paise = ₹4,000).
  - `business_objective`: Typed enum (`BALANCE_REVENUE_AND_MARGIN`, `MAXIMIZE_REVENUE`, `MAXIMIZE_CONTRIBUTION`, `INCREASE_AOV`).

### 2.2 `Product`
- **Catalog Scope**: Represents an individual SKU available for commercial sale.
- **Key Invariants**:
  - Unique composite index on `(merchant_id, sku)` to guarantee SKU uniqueness within merchant tenant.
  - `price_paise`: Strict positive integer (`> 0`). Zero or negative prices are prohibited.
  - `cost_paise`: Strict non-negative integer (`>= 0`).
  - `inventory_quantity` & `reserved_quantity`: Non-negative integers. `available_to_sell = inventory_quantity - reserved_quantity`.

### 2.3 `ProductRelationship`
- **Commercial Affinity Scope**: Encodes deterministic product relationships:
  - `COMPLEMENTARY`: Products naturally purchased together (e.g., Backpack + Laptop Sleeve).
  - `SUBSTITUTE`: Products satisfying the same intent (e.g., Standard Backpack vs. Ballistic Nylon Pack).
  - `BUNDLE_COMPONENT`: Item explicitly configured as a bundle accessory.
  - `UPSELL`: Higher-tier alternative recommended to trade up.
  - `CROSS_SELL`: Peripheral or accessory recommendation.
- **Key Invariants**:
  - Bounded to the same merchant tenant (`p1.merchant_id == p2.merchant_id`). Cross-merchant links are rejected.
  - Self-referencing links (`primary_product_id == related_product_id`) are rejected.
  - Unique constraint on `(primary_product_id, related_product_id, relationship_type)`.
  - Distinguishes provenance via `source`: `'merchant_defined'` vs. `'system_inferred'`.

### 2.4 `MerchantPriority`
- **Catalog Directives Scope**: Stores merchant-specified priority SKUs, focus categories, and clearance inventory targets.
- **Key Invariants**:
  - 1-to-1 relationship with `Merchant`.
  - Evaluated deterministically to prioritize bundles containing clearance stock.
