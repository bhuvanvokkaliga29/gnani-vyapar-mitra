# Phase 2 Security Hardening Review

This document provides a security audit of the Merchant Commerce Model, multi-tenant boundaries, secret isolation, and data validation layers.

---

## 1. Multi-Tenant Authorization & Scoping

All catalog, relationship, constraint, and priority endpoints are prefixed by `{merchant_id}`:
```text
/api/v1/merchants/{merchant_id}/...
```

### Security Controls:
1. **Tenant Enclosure**:
   - Product creation requires `merchant_id` in path; product is stored with `merchant_id`.
   - Product update (`PATCH /merchants/{merchant_id}/products/{product_id}`) verifies that `product.merchant_id == merchant_id`. If an attacker attempts to update a product belonging to another tenant, the service returns `HTTP 404 Not Found` rather than exposing foreign entity existence.
2. **Cross-Tenant Relationship Prohibition**:
   - Both products in a relationship request are retrieved and checked:
     `if p1.merchant_id != merchant_id or p2.merchant_id != merchant_id: raise InvalidRelationshipError(...)`
   - Returns `HTTP 400 Bad Request`.
3. **Database-Level Integrity**:
   - Foreign keys to `merchants.id` ensure orphaned catalog entries cannot exist.
   - `ON DELETE CASCADE` guarantees that deleting a merchant tenant cleanly removes their catalog and relationships.

---

## 2. Zero-Secret Exposure in Commerce Context

The `MerchantCommerceContext` endpoint (`GET /api/v1/merchants/{id}/commerce-context`) was inspected across all fields:
- **No Razorpay Credentials**: Does not contain `razorpay_key_id`, `razorpay_key_secret`, or any payment gateway tokens.
- **No Webhook Secrets**: Does not contain `razorpay_webhook_secret`.
- **No Database Connection Strings**: Contains zero host, port, user, or connection strings.
- **Safe Content Only**: Exposes solely commercial facts: merchant name, currency, status, objective, guardrails, catalog pricing, COGS, inventory, and relationships.

---

## 3. Input Validation & Defense-in-Depth

All incoming requests are validated by Pydantic v2 schemas:
- **String Length Limits**: ID lengths constrained (`min_length=3`, `max_length=64`).
- **Currency Format**: Constrained to ISO-4217 3-letter codes; normalized to uppercase.
- **Financial Bounds**:
  - `price_paise > 0` (strictly positive).
  - `cost_paise >= 0` (non-negative).
  - `minimum_margin_percent` bounded between `0.00` and `100.00`.
  - `maximum_discount_percent` bounded between `0.00` and `100.00`.
- **Inventory Bounds**: `reserved_quantity <= inventory_quantity` enforced at schema, service, and database levels.
- **Enumeration Whitelisting**:
  - `business_objective` restricted to: `BALANCE_REVENUE_AND_MARGIN`, `MAXIMIZE_REVENUE`, `MAXIMIZE_CONTRIBUTION`, `INCREASE_AOV`.
  - `relationship_type` restricted to: `COMPLEMENTARY`, `SUBSTITUTE`, `BUNDLE_COMPONENT`, `UPSELL`, `CROSS_SELL`.
  - `source` restricted to: `merchant_defined`, `system_inferred`.

---

## 4. Audit Trail Logging

Every mutation in the commerce subsystem is logged to the immutable `audit_events` table:
- `merchant_created`
- `constraints_updated`
- `merchant_priorities_updated`
- `product_created`
- `product_updated`
- `relationship_created`
- `commerce_context_requested`

All logs use structured key-value pairs without sensitive personal or payment credentials.
