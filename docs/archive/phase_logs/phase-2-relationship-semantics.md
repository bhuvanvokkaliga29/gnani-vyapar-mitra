# Product Relationship Semantics & Provenance

This document specifies the directional semantics, affinity scoring, and provenance rules for all product relationships supported in the Merchant Commerce Model.

---

## 1. Directional vs. Symmetric Classification

Product relationships are not uniformly symmetric. Downstream Policy Agents must respect the directional nature of specific relationship types:

| Relationship Type | Semantic Definition | Symmetry | Example |
| :--- | :--- | :---: | :--- |
| **`COMPLEMENTARY`** | Products functionally enhancing or accompanying one another. | **Symmetric** | Backpack $\leftrightarrow$ Laptop Sleeve. When A complements B, B complements A. |
| **`SUBSTITUTE`** | Products satisfying the same underlying buyer intent. | **Symmetric** | Travel Backpack $\leftrightarrow$ Executive Nylon Pack. Either can satisfy the travel bag need. |
| **`BUNDLE_COMPONENT`** | Product designed specifically as an accessory or add-on within a parent package. | **Directional** | Laptop Sleeve $\to$ Travel Backpack (Sleeve is an add-on component of the backpack bundle, but the backpack is not a sub-component of the sleeve). |
| **`UPSELL`** | Higher-tier, more premium alternative to trade the buyer up. | **Directional** | Standard Backpack $\to$ Executive Nylon Pack. If a buyer considers the Standard pack, we upsell to Executive; we do not "upsell" from Executive down to Standard. |
| **`CROSS_SELL`** | Tangentially related product offered at point of sale. | **Directional** | Wireless Mouse $\to$ Travel Backpack (Suggested as an on-the-go travel accessory). |

---

## 2. Relational Storage Rules

1. **Explicit Storage**: The database stores explicit directed tuples:
   $$\text{Tuple} = (\text{primary\_product\_id}, \text{related\_product\_id}, \text{relationship\_type})$$
2. **Symmetric Relations**: When a relationship is conceptually symmetric (e.g. `COMPLEMENTARY`), the merchant or system may either:
   - Store explicit directed edges in both directions if asymmetric affinity scores apply.
   - Rely on the Policy Agent consumer recognizing symmetric relationship types during query resolution.
3. **No Self-Links**: `primary_product_id != related_product_id` is enforced by database `CheckConstraint("chk_no_self_relationship")` and service validation.
4. **Tenant Scoping**: Both products must belong to the exact same merchant tenant. Cross-merchant links are rejected with HTTP 400.

---

## 3. Provenance and Confidence

To prevent machine-generated hypotheses from masquerading as merchant ground truth, every relationship carries:
- **`source`**:
  - `'merchant_defined'`: Manually configured by the merchant operator. Considered absolute ground truth ($\text{confidence} = 1.00$).
  - `'system_inferred'`: Inferred by analytics or co-purchase history. Treated as an empirical prior that the Policy Agent may test or discount.
- **`affinity_score`**: Normalized float between `0.00` and `1.00` representing co-purchase strength or bundling affinity.
- **`confidence`**: Normalized float between `0.00` and `1.00` representing statistical certainty of the link.
