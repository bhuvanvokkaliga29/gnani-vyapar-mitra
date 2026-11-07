# Clean-Database Rebuild Verification

**Test Execution**: Automated via `tests/integration/test_clean_db_rebuild.py::test_clean_database_rebuild_and_seed`  
**Status**: **PASS (100% verified)**  

---

## 1. Objective
Prove that the system can be completely initialized from zero on an empty database without any pre-existing state, manual database alterations, or residual configuration.

```text
EMPTY DATABASE
      ↓
SCHEMA GENERATION (Base.metadata.create_all)
      ↓
SEED DEMO MERCHANT & CATALOG
      ↓
ATLAS TRAVEL GEAR CREATED
      ↓
COMMERCE CONTEXT RETRIEVAL
```

---

## 2. Verification Protocol

The automated test executes the following sequence against an ephemeral database (`clean_rebuild_test.db`):
1. **Teardown**: Any existing `clean_rebuild_test.db` file is unlinked.
2. **Schema Creation**: SQLAlchemy executes `Base.metadata.create_all` establishing all 8 system tables:
   - `merchants`
   - `products`
   - `product_relationships`
   - `merchant_priorities`
   - `orders`
   - `payments`
   - `processed_webhook_events`
   - `audit_events`
3. **Merchant Seeding**: `merch_atlas_travel` is created with objective `BALANCE_REVENUE_AND_MARGIN`, margin floor `25.00%`, discount ceiling `8.00%`, and target AOV `₹4,000`.
4. **Catalog Seeding**: Products `prod_travel_backpack` and `prod_laptop_sleeve` are inserted with integer paise prices and COGS.
5. **Relationship Seeding**: A `COMPLEMENTARY` relationship is linked between the backpack and sleeve with affinity `0.85`.
6. **Context Validation**: `get_merchant_commerce_context("merch_atlas_travel")` is invoked and asserted to return a fully populated, valid `MerchantCommerceContext` with:
   - 2 products
   - 1 relationship
   - Correct gross margins (`39.98%` and `56.20%`)
   - `is_eligible = True` for both items.
7. **Cleanup**: The ephemeral database file is safely disposed and deleted.

---

## 3. Results Summary

```text
tests/integration/test_clean_db_rebuild.py::test_clean_database_rebuild_and_seed PASSED [100%]
```
- **Execution Time**: ~0.08s
- **Zero Manual Steps Required**: Fully autonomous schema initialization and context generation.
