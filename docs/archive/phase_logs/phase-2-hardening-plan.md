# Phase 2 Adversarial Hardening Plan: Merchant Commerce Model

## 1. Current Assumptions
1. **Source of Truth**: The database and deterministic service layer represent 100% of commercial reality. LLMs and policy agents have zero write access and cannot invent prices, costs, margins, inventory, or constraints.
2. **Deterministic Economics**: All monetary arithmetic uses integer paise (`int`). All ratios and margins use Python `Decimal` with `ROUND_HALF_UP` quantization. No floating-point math is allowed in financial pathways.
3. **Multi-Tenant Scoping**: All catalog products, affinity relationships, and constraints are strictly scoped to a single `merchant_id`. Cross-merchant operations are forbidden.
4. **Context Boundary**: The future Policy Agent interacts solely via the typed `MerchantCommerceContext` schema and never executes arbitrary database queries.

---

## 2. Identified Test & Implementation Gaps
From our architectural audit of Phase 2, we identified the following gaps:
1. **Context Collection Ordering Jitter**:
   - `list_relationships()` and `list_products()` queries did not guarantee deterministic sorting across different database engines.
   - *Fix*: Enforce deterministic sort orders: products by `id.asc()` and relationships by `(primary_product_id, related_product_id, relationship_type)`.
2. **Currency Consistency Validation**:
   - Currently, a product can be created with currency different from the merchant's base currency (e.g., `USD` product under an `INR` merchant).
   - *Fix*: Enforce currency matching at the schema and service level.
3. **Enum Validation on Objectives and Relationship Types**:
   - `business_objective` currently allows arbitrary strings in update requests.
   - `relationship_type` currently allows arbitrary strings.
   - *Fix*: Restrict `business_objective` to `{"BALANCE_REVENUE_AND_MARGIN", "MAXIMIZE_REVENUE", "MAXIMIZE_CONTRIBUTION", "INCREASE_AOV"}` and `relationship_type` to `{"COMPLEMENTARY", "SUBSTITUTE", "BUNDLE_COMPONENT", "UPSELL", "CROSS_SELL"}`.
4. **Inventory Reservation Invariant**:
   - `reserved_quantity` is not guarded against exceeding `inventory_quantity` at the model/service level.
   - *Fix*: Enforce `reserved_quantity <= inventory_quantity` on creation and update.
5. **Product Update API Missing**:
   - While `ProductUpdateRequest` existed in schemas, `PATCH /api/v1/merchants/{merchant_id}/products/{product_id}` was not exposed in the router, blocking granular update propagation tests.
   - *Fix*: Expose `PATCH /api/v1/merchants/{merchant_id}/products/{product_id}`.
6. **Strict Economic Boundary Verification**:
   - Boundary tests for exact threshold values (e.g., margin floor 25.00% vs 24.99% and discount ceiling 8.00% vs 8.01%) need explicit tests.
7. **Clean Database Rebuild Verification**:
   - Need an automated test that builds an empty database from zero, runs seeds, and queries context.
8. **Phase 3 Consumer Contract Test**:
   - Need an isolated consumer test proving that commercial reasoning can be executed on `MerchantCommerceContext` without database access.

---

## 3. Hardening Scenarios

### Scenario 1: Clean-Database Rebuild Test
- Initialize an empty temporary database (`clean_rebuild.db`).
- Execute schema migrations (`Base.metadata.create_all`).
- Execute `seed_atlas_travel()` idempotently.
- Query `get_merchant_commerce_context("merch_atlas_travel")`.
- Assert exact product count, relationship count, and economics.

### Scenario 2: Multi-Tenant Isolation
- Setup Merchant A (`merch_tenant_a`, products A1, A2) and Merchant B (`merch_tenant_b`, products B1, B2).
- Attempt: Merchant A links A1 $\leftrightarrow$ B1 (Must fail HTTP 400).
- Attempt: Merchant A modifies B1's price (Must fail HTTP 404 / 400).
- Attempt: Changing Merchant A's margin floor (Must leave Merchant B's margin floor unchanged).
- Assert: `GET /merchants/merch_tenant_a/commerce-context` contains zero products from Merchant B.

### Scenario 3: Context Determinism
- Query `GET /api/v1/merchants/{id}/commerce-context` 10 consecutive times without mutation.
- Assert identical JSON serialized payload and identical entity ordering.

### Scenario 4: Update Propagation
- Update Product Price: Context reflects new price, new profit, and new margin %.
- Update Inventory: Context reflects new available stock and eligibility.
- Update Constraints: Context reflects new margin floor and re-evaluates product eligibility.
- Update Priorities: Context reflects new priority and clearance arrays.

### Scenario 5: Economic Boundaries & Invariants
- Margin Floor: 24.99% (Reject), 25.00% (Accept), 25.01% (Accept).
- Discount Ceiling: 8.00% (Accept), 8.01% (Reject).
- Zero profit: Price == COGS (Margin = 0.00%, Profit = 0).
- Negative margin: Price < COGS (Rejected or flagged ineligible when floor > 0).
- Invariant: Price decrease with unchanged cost $\implies$ gross profit $\le$ previous gross profit.

### Scenario 6: Inventory Invariants
- `reserved > physical` rejected.
- `inventory = 0` $\implies$ `is_eligible = False`.
- `available_to_sell = inventory - reserved`.

### Scenario 7: Relationship Semantics & Provenance
- Asymmetric relationships (e.g. A is an UPSELL to B does not automatically make B an UPSELL to A).
- Provenance preservation: `merchant_defined` vs `system_inferred`.

### Scenario 8: Schema Round-Trip & Phase 3 Consumer
- Serialize `MerchantCommerceContext` to JSON, parse back into Pydantic model, verify field-for-field identity.
- Execute standalone `DummyPolicyAgentConsumer` over the context without database imports.

---

## 4. Expected Invariants
1. `gross_profit_paise == price_paise - cost_paise` always.
2. `gross_margin_percent == ((price - cost) / price) * 100` quantized to 2 decimal places.
3. `available_to_sell == inventory_quantity - reserved_quantity >= 0`.
4. `product.currency == merchant.currency`.
5. `primary_product.merchant_id == related_product.merchant_id == relationship.merchant_id`.
6. `primary_product_id != related_product_id`.
7. `MerchantCommerceContext` contains zero secrets (no API keys, no webhook tokens, no DB strings).

---

## 5. Success Criteria
- 100% of all Phase 1 regression tests continue passing (27/27).
- 100% of all Phase 2 hardening tests pass.
- Clean database rebuild verified end-to-end.
- Multi-tenant isolation verified across read, write, and relationship paths.
- Phase 3 dummy consumer successfully parses and queries context without database.
- Complete documentation package produced.
