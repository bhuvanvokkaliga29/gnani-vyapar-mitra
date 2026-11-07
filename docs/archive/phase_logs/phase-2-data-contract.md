# Phase 2: Merchant Commerce Data Contract

This document defines the input and output data contracts, Pydantic schemas, and the unified `MerchantCommerceContext` consumed by the future Policy Agent.

---

## 1. Unified Knowledge Boundary: `MerchantCommerceContext`

The future Policy Agent never executes arbitrary database queries. It receives a single, strongly-typed, deterministic context payload via `GET /api/v1/merchants/{merchant_id}/commerce-context`.

### Contract Schema:
```json
{
  "merchant_id": "merch_atlas_travel",
  "merchant_name": "Atlas Travel Gear",
  "currency": "INR",
  "status": "active",
  "business_objective": "BALANCE_REVENUE_AND_MARGIN",
  "constraints": {
    "minimum_margin_percent": "25.00",
    "maximum_discount_percent": "8.00",
    "target_aov_paise": 400000
  },
  "priorities": {
    "priority_product_ids": ["prod_travel_backpack", "prod_laptop_sleeve"],
    "priority_categories": ["Bags & Luggage"],
    "clearance_product_ids": ["prod_wireless_mouse"]
  },
  "products": [
    {
      "id": "prod_travel_backpack",
      "merchant_id": "merch_atlas_travel",
      "sku": "SKU-BACKPACK-01",
      "name": "Atlas All-Weather Travel Backpack (35L)",
      "description": "Waterproof modular backpack with ergonomic harness and dedicated laptop sleeve compartment.",
      "category": "Bags & Luggage",
      "price_paise": 299900,
      "cost_paise": 180000,
      "currency": "INR",
      "inventory_quantity": 30,
      "reserved_quantity": 0,
      "available_to_sell": 30,
      "gross_profit_paise": 119900,
      "gross_margin_percent": "39.98",
      "is_active": true,
      "is_eligible": true,
      "ineligibility_reason": null,
      "attributes": {
        "volume_liters": 35,
        "material": "Cordura 500D",
        "laptop_compat_inches": 16
      },
      "created_at": "2026-09-03T04:52:42.000000Z",
      "updated_at": "2026-09-03T04:52:42.000000Z"
    }
  ],
  "relationships": [
    {
      "id": 1,
      "merchant_id": "merch_atlas_travel",
      "primary_product_id": "prod_travel_backpack",
      "related_product_id": "prod_laptop_sleeve",
      "relationship_type": "COMPLEMENTARY",
      "affinity_score": "0.85",
      "source": "merchant_defined",
      "confidence": "1.00",
      "created_at": "2026-09-03T04:52:42.000000Z"
    }
  ],
  "generated_at": "2026-09-03T04:52:42.000000Z"
}
```

---

## 2. API Endpoints Contract

### 2.1 `POST /api/v1/merchants`
- **Request**: `MerchantCreateRequest` (`id`, `name`, `currency`, `business_objective`, `minimum_margin_percent`, `maximum_discount_percent`, `target_aov_paise`).
- **Response**: HTTP 201 Created returning `MerchantResponse`.
- **Errors**: HTTP 400 Bad Request on duplicate ID or invalid parameter bounds.

### 2.2 `GET /api/v1/merchants/{merchant_id}`
- **Response**: HTTP 200 OK returning `MerchantResponse`.
- **Errors**: HTTP 404 Not Found if merchant ID is absent.

### 2.3 `POST /api/v1/merchants/{merchant_id}/products`
- **Request**: `ProductCreateRequest` (`id`, `sku`, `name`, `category`, `price_paise`, `cost_paise`, `inventory_quantity`, `attributes`).
- **Response**: HTTP 201 Created returning `ProductResponse` with computed unit economics.
- **Errors**:
  - HTTP 404 Not Found if merchant does not exist.
  - HTTP 409 Conflict if SKU already exists for this merchant.
  - HTTP 400 Bad Request if validation rules fail (`price_paise <= 0`, `cost_paise < 0`).

### 2.4 `POST /api/v1/merchants/{merchant_id}/relationships`
- **Request**: `RelationshipCreateRequest` (`primary_product_id`, `related_product_id`, `relationship_type`, `affinity_score`, `source`).
- **Response**: HTTP 201 Created returning `RelationshipResponse`.
- **Errors**:
  - HTTP 400 Bad Request on self-referencing relationship (`primary == related`).
  - HTTP 400 Bad Request on cross-merchant relationship.
  - HTTP 400 Bad Request on duplicate relationship type.

### 2.5 `GET /api/v1/merchants/{merchant_id}/commerce-context`
- **Response**: HTTP 200 OK returning `MerchantCommerceContext`.
- **Security Guarantee**: Zero credentials, secrets, or internal engine details exposed.
