# Commerce Context Determinism & Update Propagation

**Test Execution**: Automated via `tests/integration/test_context_determinism.py`  
**Status**: **PASS (100% verified)**  

---

## 1. The Determinism Contract

Downstream agentic systems require **stable, reproducible inputs**. If two identical reads of merchant state return different JSON serialization orderings, agent caching, reasoning nodes, and decision hashes become unstable.

### Deterministic Sorting Invariants:
1. **Products**: Ordered deterministically by primary key: `ORDER BY products.id ASC`.
2. **Relationships**: Ordered deterministically by composite keys: `ORDER BY product_relationships.primary_product_id ASC, product_relationships.related_product_id ASC, product_relationships.relationship_type ASC`.
3. **Priorities**: Lists of priority SKUs, categories, and clearance targets are sorted alphabetically prior to serialization: `sorted(priority_product_ids)`.

---

## 2. Repeated Read Verification

In `test_repeated_context_calls_are_deterministic`:
- `GET /api/v1/merchants/{id}/commerce-context` was queried across 5 consecutive HTTP calls without intervening mutations.
- The payloads (excluding the ephemerally generated UTC timestamp `generated_at`) were verified to be **100% byte-for-byte identical**.
- The product list order was verified to strictly match `["prod_det_1", "prod_det_2", "prod_det_3"]`, regardless of database insert order.

---

## 3. Update Propagation Protocol

In `test_update_propagation_to_commerce_context`, foundational fields were mutated individually to verify that the authoritative database state immediately propagates to the context:

| Stage | Field Mutated | Previous State | New Value | Context Impact Verified |
| :--- | :--- | :--- | :--- | :--- |
| **Initial** | Creation | — | Price: 10000, Cost: 7000, Inv: 20 | Profit: 3000, Margin: `30.00%`, Eligible: `True` |
| **Price Update** | `price_paise` | 10000 | 20000 | Profit: 13000, Margin: `65.00%`, Eligible: `True` |
| **Stock Exhaustion** | `inventory_quantity` | 20 | 0 | Available: 0, Eligible: `False` ("Insufficient inventory") |
| **Constraint Shift** | `minimum_margin_percent` | 25.00% | 70.00% | Margin `65.00%` < `70.00%`, Eligible: `False` ("below minimum required margin") |

Zero caching lag or stale state was observed; the context directly reflects authoritative relational state on every call.
