# Minimal Relational Data Model (PostgreSQL 16)

This document defines the relational schema across two distinct functional layers:
1. **Phase 1: Transaction Domain** (Razorpay synchronization, idempotency, payments, audit)
2. **Phase 2: Merchant Commerce Domain** (Tenants, catalog, unit economics, affinity relationships, priorities)

---

## 1. Entity Relationship Overview

```text
[ PHASE 2: COMMERCE DOMAIN ]
merchants
  │
  ├──< products ──< product_relationships
  │
  └──< merchant_priorities

[ FUTURE POLICY AGENT (PHASE 3+) ]
merchants
  │
  ├──< experiments ──< experiment_variants
  │        │
  │        └──< agent_decisions
  │                  │
  ├──< buyer_intents ┘
  │        │
  │        ▼
[ PHASE 1: TRANSACTION DOMAIN ]
        orders ──< payments
           │
  audit_events
  [processed_webhook_events] (standalone idempotency ledger)
```

---

## 2. Table Specifications

### DOMAIN A: PHASE 2 MERCHANT COMMERCE MODEL

### 2.1 `merchants`
- **Purpose**: Represents the merchant tenant operating the policy agent.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (e.g., `'merch_artisanal_brew_99'`)
  - `name`: VARCHAR(255) NOT NULL
  - `currency`: VARCHAR(3) NOT NULL DEFAULT `'INR'`
  - `razorpay_key_id`: VARCHAR(128) NOT NULL (encrypted or env-referenced)
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Constraints**: Currency must be valid ISO 4217 (`INR`).

### 2.2 `products`
- **Purpose**: Stores the merchant catalog with unit economics and inventory.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (e.g., `'prod_coffee_maker_01'`)
  - `merchant_id`: VARCHAR(64) NOT NULL REFERENCES `merchants(id)` ON DELETE CASCADE
  - `sku`: VARCHAR(64) NOT NULL
  - `name`: VARCHAR(255) NOT NULL
  - `category`: VARCHAR(64) NOT NULL
  - `attributes`: JSONB NOT NULL DEFAULT `'{}'`::jsonb
  - `base_price_paise`: BIGINT NOT NULL CHECK (base_price_paise > 0)
  - `cogs_paise`: BIGINT NOT NULL CHECK (cogs_paise >= 0)
  - `inventory_count`: INT NOT NULL DEFAULT 0 CHECK (inventory_count >= 0)
  - `is_active`: BOOLEAN NOT NULL DEFAULT TRUE
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - UNIQUE INDEX `idx_products_merchant_sku` (`merchant_id`, `sku`)
  - INDEX `idx_products_category` (`category`)

### 2.3 `product_relationships`
- **Purpose**: Encodes SKU affinity and bundling rules (e.g., accessory compatibility).
- **Fields**:
  - `id`: BIGSERIAL PRIMARY KEY
  - `primary_product_id`: VARCHAR(64) NOT NULL REFERENCES `products(id)` ON DELETE CASCADE
  - `related_product_id`: VARCHAR(64) NOT NULL REFERENCES `products(id)` ON DELETE CASCADE
  - `relationship_type`: VARCHAR(32) NOT NULL (`'compatible_accessory'`, `'bundle_addon'`)
  - `bundle_affinity_score`: NUMERIC(3, 2) NOT NULL DEFAULT 0.50
- **Constraints**:
  - UNIQUE (`primary_product_id`, `related_product_id`, `relationship_type`)
  - CHECK (`primary_product_id` != `related_product_id`)

### 2.4 `merchant_policies`
- **Purpose**: Stores the active economic guardrails and business rules defined by the merchant.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY
  - `merchant_id`: VARCHAR(64) NOT NULL REFERENCES `merchants(id)` ON DELETE CASCADE
  - `margin_floor_pct`: NUMERIC(5, 2) NOT NULL CHECK (margin_floor_pct >= 0 AND margin_floor_pct <= 100)
  - `max_discount_ceiling_pct`: NUMERIC(5, 2) NOT NULL CHECK (max_discount_ceiling_pct >= 0 AND max_discount_ceiling_pct <= 100)
  - `allow_bundling`: BOOLEAN NOT NULL DEFAULT TRUE
  - `max_bundle_size`: INT NOT NULL DEFAULT 3
  - `is_active`: BOOLEAN NOT NULL DEFAULT TRUE
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()

### 2.5 `buyer_intents`
- **Purpose**: Stores ingested AI buyer queries and normalized extracted constraints.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (e.g., `'int_7f8a9b1c2d'`)
  - `merchant_id`: VARCHAR(64) NOT NULL REFERENCES `merchants(id)`
  - `buyer_id`: VARCHAR(64) NOT NULL
  - `buyer_persona`: VARCHAR(32) NOT NULL (`'budget_sensitive'`, `'premium'`, etc.)
  - `raw_query`: TEXT NOT NULL
  - `extracted_constraints`: JSONB NOT NULL
  - `is_simulated`: BOOLEAN NOT NULL DEFAULT FALSE
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - INDEX `idx_intents_merchant_sim` (`merchant_id`, `is_simulated`)

### 2.6 `experiments` & `experiment_variants`
- **Purpose**: Tracks live policy experiments (e.g., Control Single SKU vs Variant Bundles).
- **`experiments` Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (e.g., `'exp_espresso_bundling_v1'`)
  - `merchant_id`: VARCHAR(64) NOT NULL REFERENCES `merchants(id)`
  - `name`: VARCHAR(255) NOT NULL
  - `status`: VARCHAR(32) NOT NULL DEFAULT `'RUNNING'` (`'DRAFT'`, `'RUNNING'`, `'COMPLETED'`)
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **`experiment_variants` Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (e.g., `'var_bundle_b'`)
  - `experiment_id`: VARCHAR(64) NOT NULL REFERENCES `experiments(id)` ON DELETE CASCADE
  - `variant_key`: VARCHAR(32) NOT NULL (`'CONTROL'`, `'VARIANT_A'`, `'VARIANT_B'`)
  - `allocation_pct`: NUMERIC(5, 2) NOT NULL DEFAULT 33.33
  - `strategy_template`: JSONB NOT NULL
  - `sample_count`: INT NOT NULL DEFAULT 0
  - `conversion_count`: INT NOT NULL DEFAULT 0
  - `total_observed_contribution_paise`: BIGINT NOT NULL DEFAULT 0

### 2.7 `agent_decisions`
- **Purpose**: Records every individual agent strategy proposal and deterministic validation verdict.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (e.g., `'dec_9e8d7c6b5a'`)
  - `merchant_id`: VARCHAR(64) NOT NULL REFERENCES `merchants(id)`
  - `intent_id`: VARCHAR(64) NOT NULL REFERENCES `buyer_intents(id)`
  - `experiment_variant_id`: VARCHAR(64) REFERENCES `experiment_variants(id)`
  - `proposed_strategy`: JSONB NOT NULL
  - `qualitative_reasoning`: TEXT
  - `predicted_selection_probability`: NUMERIC(4, 3)
  - `predicted_contribution_paise`: BIGINT
  - `is_approved`: BOOLEAN NOT NULL
  - `rejection_reasons`: JSONB NOT NULL DEFAULT `'[]'`::jsonb
  - `approved_strategy`: JSONB
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - INDEX `idx_decisions_intent` (`intent_id`)

### 2.8 `orders`
- **Purpose**: Manages internal orders and correlates with Razorpay Order objects.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (Internal Order ID)
  - `decision_id`: VARCHAR(64) NOT NULL UNIQUE REFERENCES `agent_decisions(id)`
  - `merchant_id`: VARCHAR(64) NOT NULL REFERENCES `merchants(id)`
  - `razorpay_order_id`: VARCHAR(64) UNIQUE
  - `amount_paise`: BIGINT NOT NULL CHECK (amount_paise > 0)
  - `currency`: VARCHAR(3) NOT NULL DEFAULT `'INR'`
  - `receipt`: VARCHAR(40) NOT NULL UNIQUE (mapped to `decision_id`)
  - `status`: VARCHAR(32) NOT NULL DEFAULT `'CREATED'` (`'CREATED'`, `'PAID'`, `'FAILED'`, `'EXPIRED'`)
  - `is_simulated`: BOOLEAN NOT NULL DEFAULT FALSE
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - INDEX `idx_orders_razorpay_id` (`razorpay_order_id`)
  - INDEX `idx_orders_receipt` (`receipt`)

### 2.9 `payments`
- **Purpose**: Tracks payment captures received from Razorpay webhooks or API reconciliation.
- **Fields**:
  - `id`: VARCHAR(64) PRIMARY KEY (Razorpay Payment ID, e.g., `'pay_PLM992817x'`)
  - `order_id`: VARCHAR(64) NOT NULL REFERENCES `orders(id)`
  - `amount_paise`: BIGINT NOT NULL
  - `currency`: VARCHAR(3) NOT NULL
  - `status`: VARCHAR(32) NOT NULL (`'captured'`, `'failed'`, `'authorized'`)
  - `method`: VARCHAR(32)
  - `captured_at`: TIMESTAMPTZ
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()

### 2.10 `processed_webhook_events`
- **Purpose**: Idempotency ledger preventing double-processing of duplicate webhooks.
- **Fields**:
  - `event_id`: VARCHAR(128) PRIMARY KEY (from `X-Razorpay-Event-Id`)
  - `event_type`: VARCHAR(64) NOT NULL
  - `payload`: JSONB NOT NULL
  - `processed_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()

### 2.11 `audit_events`
- **Purpose**: Immutable append-only audit trail recording every state change and decision.
- **Fields**:
  - `id`: BIGSERIAL PRIMARY KEY
  - `entity_type`: VARCHAR(32) NOT NULL (`'DECISION'`, `'ORDER'`, `'POLICY'`, `'PAYMENT'`)
  - `entity_id`: VARCHAR(64) NOT NULL
  - `actor`: VARCHAR(32) NOT NULL (`'AGENT'`, `'POLICY_ENGINE'`, `'RAZORPAY_WEBHOOK'`)
  - `action`: VARCHAR(64) NOT NULL
  - `event_payload`: JSONB NOT NULL
  - `created_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - INDEX `idx_audit_entity` (`entity_type`, `entity_id`)
