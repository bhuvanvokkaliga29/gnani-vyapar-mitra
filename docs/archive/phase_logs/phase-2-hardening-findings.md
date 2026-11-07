# Phase 2 Hardening Findings & Defect Resolution

This document records the defects, consistency gaps, and invariants identified and fixed during the Phase 2 adversarial hardening pass.

---

## Finding 1: Nondeterministic Collection Ordering in Commerce Context

- **Severity**: Medium
- **Reproduction**: Repeated calls to `GET /api/v1/merchants/{id}/commerce-context` on databases without guaranteed primary key scan order yielded nondeterministic array orderings for `products` and `relationships`.
- **Root Cause**: `select(ProductRelationship).where(...)` omitted an explicit SQL `order_by` clause.
- **Fix**: Added explicit deterministic sort clauses:
  - Products: `.order_by(Product.id.asc())`
  - Relationships: `.order_by(ProductRelationship.primary_product_id.asc(), ProductRelationship.related_product_id.asc(), ProductRelationship.relationship_type.asc())`
  - Priorities: Sorted arrays (`sorted(priority_product_ids)`) before context assembly.
- **Regression Test**: `tests/integration/test_context_determinism.py::test_repeated_context_calls_are_deterministic`
- **Status**: **RESOLVED & VERIFIED**

---

## Finding 2: Currency Mismatch Allowed Between Product and Merchant

- **Severity**: High
- **Reproduction**: A product could be created with `currency="USD"` under a merchant configured with `currency="INR"`, corrupting unit economics.
- **Root Cause**: `CommerceService.create_product` did not validate that `product.currency == merchant.currency`.
- **Fix**: Added strict assertion in `CommerceService.create_product`:
  ```python
  if req.currency.upper() != merchant.currency.upper():
      raise CommerceServiceError(f"Product currency '{req.currency.upper()}' does not match merchant base currency '{merchant.currency.upper()}'")
  ```
- **Regression Test**: `tests/integration/test_commerce_edge_cases.py` and `tests/unit/test_commerce_models.py`
- **Status**: **RESOLVED & VERIFIED**

---

## Finding 3: Unconstrained Enums on Objectives and Relationships

- **Severity**: Medium
- **Reproduction**: Passing arbitrary strings (e.g. `business_objective="CUSTOM_GOAL"`, `relationship_type="SIBLING"`, or `source="ai_hallucination"`) was accepted by Pydantic schemas.
- **Root Cause**: Fields used untyped `str` annotations without Pydantic `@field_validator` whitelist checking.
- **Fix**: Added `@field_validator` on `MerchantCreateRequest`, `ConstraintsUpdateRequest`, and `RelationshipCreateRequest` restricting inputs to validated constant sets (`VALID_OBJECTIVES`, `VALID_RELATIONSHIP_TYPES`, `VALID_RELATIONSHIP_SOURCES`).
- **Regression Test**: `tests/unit/test_economic_boundaries.py::test_merchant_objective_enums` and `test_relationship_type_enums`
- **Status**: **RESOLVED & VERIFIED**

---

## Finding 4: Missing Product Update Endpoint

- **Severity**: Medium
- **Reproduction**: Granular update propagation testing could not update individual product prices, costs, or inventory without direct SQL execution.
- **Root Cause**: Schema had `ProductUpdateRequest`, but `apps/api/routers/merchants.py` lacked a `PATCH /{merchant_id}/products/{product_id}` route.
- **Fix**: Implemented `CommerceService.update_product` and exposed `PATCH /api/v1/merchants/{merchant_id}/products/{product_id}` with tenant verification (HTTP 404 if product does not belong to merchant).
- **Regression Test**: `tests/integration/test_context_determinism.py::test_update_propagation_to_commerce_context`
- **Status**: **RESOLVED & VERIFIED**

---

## Finding 5: Inventory Reservation Upper Bound Invariant

- **Severity**: Low
- **Reproduction**: `reserved_quantity > inventory_quantity` could be persisted if unvalidated.
- **Root Cause**: Database constraint only checked `reserved_quantity >= 0`.
- **Fix**: Added model validator in `ProductCreateRequest` and `ProductUpdateRequest` and service validation ensuring `reserved_quantity <= inventory_quantity`.
- **Regression Test**: `tests/unit/test_commerce_economics.py::test_available_to_sell`
- **Status**: **RESOLVED & VERIFIED**
