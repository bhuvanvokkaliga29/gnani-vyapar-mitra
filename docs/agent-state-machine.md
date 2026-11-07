# Agent State Machine Specification

This document specifies the complete 9-stage lifecycle of the **Merchant Policy Agent**. The execution pipeline is implemented as a single, coherent, deterministic state machine with an isolated probabilistic generation stage.

---

## 1. High-Level State Flow

```text
[INTENT] ──> [CONTEXT] ──> [GENERATE] ──> [VALIDATE] ──> [APPROVE / REJECT]
                                                                │
                   ┌────────────────────────────────────────────┴───────────────────────────┐
                   ▼ [APPROVED]                                                             ▼ [REJECTED]
               [EXECUTE]                                                             [FALLBACK / LOG]
                   │                                                                        │
                   ▼                                                                        ▼
               [OBSERVE] ──> [EVALUATE] ──> [LEARN] ─────────────────────────────────> [END RUN]
```

---

## 2. Stage-by-Stage Operational Specification

### Stage 1: INTENT
- **Purpose**: Receive natural-language buyer query or structured quote request; extract normalized constraints.
- **Input**: Raw text or ACP request (`buyer_id`, query string, declared budget, channel metadata).
- **Output**: Validated `BuyerIntent` object with typed constraints (budget in paise, categories, spec requirements).
- **Component**: Intent Parser (LLM with strict Pydantic JSON schema).
- **Nature**: Probabilistic (extraction) + Deterministic (schema parsing).
- **Failure Conditions**: Malformed JSON, unparsable query, zero or negative budget.
- **Recovery Behavior**: Fall back to generic keyword search or reject query gracefully with HTTP 400.
- **Audit Fields**: `intent_id`, `raw_query`, `extracted_constraints`, `parsing_latency_ms`.

### Stage 2: CONTEXT
- **Purpose**: Hydrate merchant-specific ground truth: active catalog, real-time inventory, COGS, margin rules, and experiment assignment.
- **Input**: `merchant_id`, `intent_id`.
- **Output**: `EnrichedContext` containing compatible SKUs, active stock counts, margin floors, and active `experiment_variant`.
- **Component**: Commerce Engine (Database query / SQL repository).
- **Nature**: Purely Deterministic.
- **Failure Conditions**: Database connection error, merchant not found, zero matching inventory.
- **Recovery Behavior**: If merchant inactive, abort; if no inventory matches, return "out-of-stock" response without invoking LLM.
- **Audit Fields**: `context_id`, `eligible_sku_count`, `experiment_variant`, `db_read_latency_ms`.

### Stage 3: GENERATE
- **Purpose**: Synthesize a commercial proposal (product selection, bundling, incentive framing, value proposition) optimized for the AI buyer persona.
- **Input**: `BuyerIntent` + `EnrichedContext`.
- **Output**: `CandidateCommercialStrategy` (unvalidated proposal).
- **Component**: Policy Agent (LLM Strategy Generator).
- **Nature**: Probabilistic.
- **Failure Conditions**: Model timeout, rate limit, schema mismatch, non-JSON response.
- **Recovery Behavior**: Fall back immediately to merchant's static baseline catalog offer (Control Variant).
- **Audit Fields**: `candidate_id`, `prompt_tokens`, `completion_tokens`, `model_name`, `candidate_json`.

### Stage 4: VALIDATE
- **Purpose**: Programmatically audit candidate proposal against all merchant business rules and physical constraints.
- **Input**: `CandidateCommercialStrategy` + Merchant Economic Guardrails.
- **Output**: `ValidationResult` (Boolean flag + detailed arithmetic calculations).
- **Component**: Deterministic Policy Engine.
- **Nature**: Purely Deterministic.
- **Failure Conditions**:
  - `effective_margin < margin_floor`
  - `bundle_discount > discount_ceiling`
  - `total_price > buyer_budget`
  - `requested_quantity > stock_level`
  - Computed sum doesn't match total
- **Recovery Behavior**: If any check fails, flag as `REJECTED` with specific constraint violation codes.
- **Audit Fields**: `validation_id`, `margin_floor_passed`, `discount_ceiling_passed`, `budget_passed`, `inventory_passed`.

### Stage 5: APPROVE / REJECT
- **Purpose**: Gating decision branch. Routes approved proposals to transaction execution, or executes deterministic fallback.
- **Input**: `ValidationResult`.
- **Output**: Approved strategy OR Fallback baseline strategy.
- **Component**: Policy Router.
- **Nature**: Purely Deterministic.
- **Failure Conditions**: N/A (binary logic).
- **Recovery Behavior**: If candidate is rejected, the fallback baseline is validated; if baseline is safe, it proceeds; otherwise transaction aborts safely.
- **Audit Fields**: `routing_decision`, `rejection_reasons`, `fallback_applied`.

### Stage 6: EXECUTE
- **Purpose**: Register the transaction order with Razorpay test-mode API.
- **Input**: Approved Strategy (`amount` in paise, `currency`, `receipt = candidate_id`).
- **Output**: Razorpay Order (`order_id`, `status: created`).
- **Component**: Razorpay Adapter.
- **Nature**: Purely Deterministic.
- **Failure Conditions**: Razorpay gateway timeout, network partition, invalid API credentials.
- **Recovery Behavior**: Never blindly retry creation. Check internal order store by `receipt` ID; if order exists, resume; if timeout persists, return error to client and log.
- **Audit Fields**: `razorpay_order_id`, `amount_paise`, `receipt_id`, `api_response_status`.

### Stage 7: OBSERVE
- **Purpose**: Ingest checkout outcome from the buyer.
- **Primary Signal**: Razorpay Webhook (`order.paid` or `payment.captured`) with HMAC SHA256 verification.
- **Secondary Signal**: API reconciliation (`GET /v1/orders/{id}/payments`).
- **Output**: Verified `TransactionOutcome` record.
- **Component**: Webhook Ingestion & Reconciliation Service.
- **Nature**: Purely Deterministic.
- **Failure Conditions**: Invalid webhook signature, duplicate `X-Razorpay-Event-Id`, webhook delivery timeout.
- **Recovery Behavior**:
  - Invalid signature -> HTTP 400 rejection.
  - Duplicate event -> HTTP 200 acknowledge without re-processing (idempotency).
  - Webhook delay -> Asynchronous reconciliation poller verifies state via API.
- **Audit Fields**: `event_id`, `payment_id`, `transaction_status`, `signature_verified`.

### Stage 8: EVALUATE
- **Purpose**: Calculate true unit economics and compare observed outcome against candidate prediction.
- **Input**: `TransactionOutcome` + Merchant Product Costs.
- **Output**: Realized Contribution, Margin %, and Conversion Flag ($1$ or $0$).
- **Component**: Economics Evaluator.
- **Nature**: Purely Deterministic.
- **Failure Conditions**: Missing COGS data for custom bundle item.
- **Recovery Behavior**: Flag record for manual merchant audit; log warning.
- **Audit Fields**: `evaluation_id`, `observed_contribution_paise`, `observed_margin_pct`, `prediction_error`.

### Stage 9: LEARN
- **Purpose**: Update policy performance statistics (variant conversion rate, average contribution, bandit weights) in the Merchant Policy Store.
- **Input**: `EvaluationRecord` + Experiment Registry.
- **Output**: Updated Policy Weights and Variant Statistics.
- **Component**: Policy Learning Service.
- **Nature**: Deterministic statistical update (Bayesian / Thompson sampling or empirical average).
- **Failure Conditions**: Concurrent write lock contention.
- **Recovery Behavior**: Standard database retry with exponential backoff.
- **Audit Fields**: `policy_version`, `updated_sample_size`, `updated_expected_contribution_paise`.
