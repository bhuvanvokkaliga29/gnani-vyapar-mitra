# Multi-Tenant Isolation Verification

**Test Execution**: Automated via `tests/integration/test_tenant_isolation.py::test_multi_tenant_complete_isolation`  
**Status**: **PASS (100% verified)**  

---

## 1. Multi-Tenant Architecture Principles

The Merchant Policy Agent operates as a multi-tenant platform where each merchant is an autonomous commercial entity. The commercial knowledge layer guarantees strict segregation across:
1. **Catalog Namespace**: Products and SKUs are strictly scoped by `merchant_id`.
2. **Context Isolation**: A tenant's context endpoint (`GET /api/v1/merchants/{id}/commerce-context`) must never leak or reference another merchant's catalog, constraints, or relationships.
3. **Relationship Boundaries**: A relationship between products belonging to different merchants is strictly prohibited.
4. **Update Boundaries**: A merchant can never read, update, or mutate another tenant's products, constraints, or priorities.

---

## 2. Hardening Test Matrix

| Isolation Boundary | Tested Action | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Context Read Isolation** | Query `GET /merchants/merch_iso_a/commerce-context` | Contains ONLY `prod_a1`, `prod_a2` | Exactly `{prod_a1, prod_a2}`; $0$ items from B | **PASS** |
| **Product Mutation Guard** | Merchant A attempts `PATCH /merchants/merch_iso_a/products/prod_b1` | HTTP 404 Not Found | HTTP 404 Not Found | **PASS** |
| **Cross-Tenant Relationship** | Merchant A attempts to link `prod_a1` $\leftrightarrow$ `prod_b1` | HTTP 400 Bad Request ("Cross-merchant product relationships are prohibited") | HTTP 400 Bad Request | **PASS** |
| **Constraint Isolation** | Update Merchant A's minimum margin from `20.00%` $\to$ `45.00%` | Merchant B's margin floor remains unchanged at `35.00%` | Merchant B remains `35.00%` | **PASS** |
| **Priority Isolation** | Set Merchant A priority products to `["prod_a1"]` | Merchant B priority products remains empty `[]` | Merchant B remains `[]` | **PASS** |

---

## 3. Database Constraints Supporting Isolation
- **Composite Unique Index**: `UniqueConstraint("merchant_id", "sku", name="uq_products_merchant_sku")` allows different merchants to use identical SKU names (e.g. `COMMON-SKU`) without database collisions while guaranteeing uniqueness within the tenant.
- **Foreign Key Cascades**: `ForeignKey("merchants.id", ondelete="CASCADE")` ensures relational integrity.
- **Service Verification**: `CommerceService.create_product_relationship()` explicitly queries `p1.merchant_id == merchant_id and p2.merchant_id == merchant_id` before committing any relationship.
