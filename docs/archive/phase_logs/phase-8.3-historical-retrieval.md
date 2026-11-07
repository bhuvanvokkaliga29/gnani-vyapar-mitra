# Phase 8.3 Historical Retrieval: APIs & Aggregations

## 1. Overview

Phase 8.3 provides deterministic query and retrieval endpoints over stored historical policy observations. It allows later components (Phase 8.4) to inspect historical policy performance across buyer contexts without mutating merchant policies or making subjective recommendations.

---

## 2. API Endpoints

### `POST /api/v1/memory/record`
Persists a validated Phase 8.1 evidence record into historical memory.
- **Request**:
  ```json
  {
    "evidence_id": "evi_8f7b2c9a1d3e",
    "merchant_id": "merch_atlas_travel"
  }
  ```
- **Behavior**: Sourced authoritatively from the database; client cannot pass reward or eligibility values.
- **Idempotency**: Replayed requests return the existing record (`201 Created`).

### `GET /api/v1/memory/{memory_id}?merchant_id={merchant_id}`
Fetches an individual historical observation by ID.
- **Tenant Scoping**: Access is strictly scoped to the requesting merchant; cross-tenant requests return `403 Forbidden`.

### `GET /api/v1/memory`
Queries historical observations matching filter parameters.
- **Query Parameters**:
  - `merchant_id` (required)
  - `policy_id` (optional)
  - `policy_version` (optional)
  - `buyer_context_key` (optional)
  - `experiment_id` (optional)
  - `variant` (optional)
  - `evidence_source` (optional)
  - `learning_eligible_only` (optional boolean)
  - `is_admissible_only` (optional boolean)
  - `start_time`, `end_time` (optional ISO 8601)
  - `limit` (default 50, max 500)
  - `offset` (default 0)
- **Deterministic Ordering**: Sorted deterministically by `observed_at DESC, id ASC`.

### `GET /api/v1/memory/summary/policy`
Retrieves factual historical summary metrics for a policy under a context or merchant-wide.
- **Query Parameters**:
  - `merchant_id` (required)
  - `policy_id` (required)
  - `buyer_context_key` (optional)
  - `policy_version` (optional)
- **Response**:
  ```json
  {
    "merchant_id": "merch_atlas_travel",
    "policy_id": "prop_treat_atlas_bundle",
    "policy_version": "merchant-policy/v1",
    "buyer_context_key": "bck_travel_backpack_TIER_MID_2K_4K_7e3a9c4f12d0",
    "total_opportunities": 50,
    "eligible_opportunities": 50,
    "ineligible_opportunities": 0,
    "guardrail_violations": 0,
    "is_policy_admissible": true,
    "order_created_count": 25,
    "converted_payments": 24,
    "conversion_rate": 0.48,
    "total_realized_revenue_paise": 8397600,
    "total_realized_cogs_paise": 4080000,
    "total_contribution_paise": 4317600,
    "contribution_per_shopper_paise": 86352,
    "contribution_per_shopper_decimal": 86352.0,
    "average_margin_percent": 51.41,
    "earliest_observed_at": "2026-09-01T10:00:00Z",
    "latest_observed_at": "2026-09-03T13:00:00Z"
  }
  ```

---

## 3. Strict Boundary: Facts Only

The summary endpoint provides **historical facts only**.
- It does **not** declare a "winning" policy.
- It does **not** rank policies.
- It does **not** make recommendations.
- It does **not** select the next policy for execution.
- These operations are strictly deferred to Phase 8.4+.
