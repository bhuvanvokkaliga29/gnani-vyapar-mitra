# Phase 2 Final Report: Merchant Commerce Model

**Project**: Merchant Policy Agent  
**Buildathon**: Razorpay AI Buildathon 2026 (Track 01: AI Growth & Agentic Commerce)  
**Date**: September 3, 2026  
**Status**: **100% COMPLETE & FULLY VERIFIED (PASS)**  

---

## 1. Objective

Phase 2 established the **merchant's deterministic commercial knowledge layer**. It provides the single source of truth for catalog items, retail pricing, unit COGS, physical inventory, product affinity relationships, merchant optimization objectives, and financial guardrails. This layer guarantees that future policy agents and LLMs will never hallucinate or invent commercial reality.

---

## 2. Implemented Domain

The commerce domain is implemented as a standalone, deterministic subsystem (`domain/models.py`, `domain/economics.py`, `services/commerce_service.py`, `apps/api/routers/merchants.py`). It cleanly decouples business rules from the Phase 1 Razorpay transaction foundation while providing a typed boundary for future phases.

---

## 3. Merchant Model

- **Entity**: `Merchant`
- **Fields**: `id`, `name`, `currency` (ISO-4217), `status`, `business_objective`, `minimum_margin_percent`, `maximum_discount_percent`, `target_aov_paise`, `created_at`, `updated_at`.
- **Invariants**: Strict range bounds on margin floors ($0 \le M \le 100$) and discount ceilings ($0 \le D \le 100$). Target AOV represented in integer paise.

---

## 4. Product Model

- **Entity**: `Product`
- **Fields**: `id`, `merchant_id`, `sku`, `name`, `description`, `category`, `price_paise`, `cost_paise`, `currency`, `inventory_quantity`, `reserved_quantity`, `is_active`, `attributes`, `created_at`, `updated_at`.
- **Invariants**: Unique index on `(merchant_id, sku)`. Check constraints: `price_paise > 0`, `cost_paise >= 0`, `inventory_quantity >= 0`, `reserved_quantity >= 0`.

---

## 5. Economics

- **Zero Float Arithmetic**: All money stored in integer paise.
- **Formulas**:
  - Gross profit: `price_paise - cost_paise`
  - Gross margin: `((price - cost) / price) * 100` evaluated using arbitrary-precision `decimal.Decimal` with `ROUND_HALF_UP` to 2 decimal places.
  - Basket effective discount: `(promotional_discount / baseline_revenue) * 100`.
- **Expected vs. Observed Contribution**: Strict conceptual separation preserved. Deterministic calculation primitives implemented without conflating ex-ante estimates with ex-post confirmed payments.

---

## 6. Inventory

- **Deterministic Availability**: `available_to_sell = inventory_quantity - reserved_quantity`.
- **Stock Eligibility**: Products with `available_to_sell <= 0` or `is_active = False` are deterministically flagged as ineligible for recommendation.

---

## 7. Relationships

- **Entity**: `ProductRelationship`
- **Types**: `COMPLEMENTARY`, `SUBSTITUTE`, `BUNDLE_COMPONENT`, `UPSELL`, `CROSS_SELL`.
- **Provenance**: `source` captures `'merchant_defined'` vs. `'system_inferred'`.
- **Integrity**: Self-relationships and cross-merchant relationships are rejected at both service and database levels.

---

## 8. Constraints

- **Financial Guardrails**: Minimum margin floor, maximum promotional discount ceiling, target AOV.
- **Basket Evaluation**: `evaluate_basket_economics()` tests proposed bundles against guardrails, returning structured violation reasons.

---

## 9. Commerce Context

- **Endpoint**: `GET /api/v1/merchants/{merchant_id}/commerce-context`
- **Payload**: Unified `MerchantCommerceContext` containing merchant profile, constraints, catalog items with computed unit economics & stock eligibility, affinity relationships, and catalog priorities.
- **Zero Secrets**: Completely isolated from API keys, webhook secrets, or internal engine details.

---

## 10. API Surface

- `POST /api/v1/merchants` — Register merchant tenant.
- `GET /api/v1/merchants/{merchant_id}` — Retrieve merchant profile.
- `PUT /api/v1/merchants/{merchant_id}/constraints` — Update guardrails.
- `PUT /api/v1/merchants/{merchant_id}/priorities` — Update catalog priorities.
- `POST /api/v1/merchants/{merchant_id}/products` — Create catalog product.
- `GET /api/v1/merchants/{merchant_id}/products` — List products with computed economics.
- `POST /api/v1/merchants/{merchant_id}/relationships` — Define product affinity.
- `GET /api/v1/merchants/{merchant_id}/commerce-context` — Retrieve unified commercial context.

---

## 11. Database Changes

Added tables to PostgreSQL/SQLite schema:
- `merchants`
- `products`
- `product_relationships`
- `merchant_priorities`
All Phase 1 transaction tables (`orders`, `payments`, `processed_webhook_events`, `audit_events`) remain completely unchanged.

---

## 12. Seed Data

- **Demo Merchant**: **Atlas Travel Gear** (`merch_atlas_travel`).
- **5 SKUs**:
  1. Atlas All-Weather Travel Backpack (35L) — ₹2,999 (COGS: ₹1,800, Stock: 30)
  2. Shock-Resistant 16-Inch Laptop Sleeve — ₹799 (COGS: ₹350, Stock: 50)
  3. Ergonomic Multi-Device Bluetooth Mouse — ₹999 (COGS: ₹500, Stock: 40)
  4. 7-in-1 Aluminum USB-C Travel Hub — ₹1,499 (COGS: ₹700, Stock: 25)
  5. Atlas Executive Ballistic Nylon Pack (42L) — ₹4,999 (COGS: ₹2,800, Stock: 15)
- **5 Seeded Relationships**: Complementary, substitute, bundle component, upsell.
- **Seed Script**: `scripts/seed_commerce_data.py` runs idempotently.

---

## 13. Security

- Multi-tenant data isolation strictly enforced (SKUs scoped per merchant, cross-merchant relationships prohibited).
- Zero credentials or internal secrets exposed in API responses or commerce context.
- Immutable append-only audit trail logs all merchant, product, and relationship events.

---

## 14. Tests

- **Total Automated Tests**: 45 passed (100%).
- **New Phase 2 Tests**: 18 tests covering economics formulas, decimal precision, schema bounds, API endpoints, and edge cases.

---

## 15. Phase 1 Regression Results

**Zero Regressions.** All 27 Phase 1 automated tests (orders API, real provider webhooks, timeout reconciliation, chaos scenarios) pass cleanly without modification.

---

## 16. Known Limitations

- Catalog seed data is synthetic for demonstration purposes.

---

## 17. Deviations from Phase 0

**None.** Implemented exactly per the approved Phase 0 specifications.

---

## 18. Phase 3 Readiness

The deterministic commercial knowledge layer is complete and fully verified. The system is completely prepared for **Phase 3: Buyer Intent Engine**.

---

## 19. Phase 2 Final Status Evaluation

```text
PHASE 2 STATUS

Merchant model:             PASS
Catalog model:              PASS
Economics:                  PASS
Inventory:                  PASS
Relationships:              PASS
Constraints:                PASS
Commerce context:           PASS
API contract:               PASS
Database migrations:        PASS
Security:                   PASS
Phase 1 regression:         PASS
Automated tests:            PASS

FINAL RECOMMENDATION:
READY FOR PHASE 3 (Deterministic commerce foundation complete)

BLOCKERS:
NONE.

KNOWN LIMITATIONS:
Demo catalog data is synthetic.
```

---

*(Per Section 41 instructions, execution is stopped here. Phase 3 implementation will begin only after formal review and approval).*
