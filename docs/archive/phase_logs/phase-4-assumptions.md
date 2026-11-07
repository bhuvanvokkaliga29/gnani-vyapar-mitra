# Phase 4 Assumptions & Verification

**Project**: Merchant Policy Agent (Razorpay AI Buildathon 2026 Track 01)  
**Phase**: Phase 4 — Merchant Policy Agent & Commercial Strategy Generation  
**Date**: September 3, 2026  

---

## 1. Razorpay Assumptions & Boundary Verification

### What Razorpay Provides
1. **Transaction Rails**: Razorpay creates orders (`POST /v1/orders`), presents test/live checkout sheets, receives card/UPI/netbanking payments, and sends signed webhooks (`order.paid`, `payment.captured`, `payment.failed`).
2. **Deterministic Minor Units**: All Razorpay transactions are processed in integer minor units (paise in INR, cents in USD).
3. **External Payment Status**: Razorpay provides cryptographically signed HMAC SHA-256 webhook payloads verifying financial finality.

### What Razorpay Does NOT Provide
The following are application-level merchant commerce domains and are NOT provided or managed by Razorpay APIs:
1. **Merchant Margins & Unit Economics**: Razorpay has no knowledge of merchant COGS, gross margins, margin floors, or cost structures.
2. **Product Catalog & Inventory**: Razorpay does not manage physical SKU stock, reserved inventory, or available-to-sell thresholds.
3. **Product Relationships**: Razorpay does not know which products are `COMPLEMENTARY`, `SUBSTITUTE`, or `BUNDLE_COMPONENT`.
4. **Buyer Intent & Natural Language**: Razorpay does not extract requirements, preferences, or negative constraints from buyer text.
5. **Commercial Policy Optimization**: Razorpay does not choose whether a merchant should offer a single item, complementary bundle, or non-price incentive.

**Architectural Consequence**:
The Policy Agent reasons strictly over our internal `MerchantCommerceContext` and `BuyerIntent`. Razorpay is exclusively the downstream financial execution and outcome ledger.

---

## 2. Inviolable Boundary Invariants

### "THE LLM CAN PROPOSE. IT CANNOT SPEND."
1. The Policy Agent **never calls Razorpay APIs**.
2. The Policy Agent **never creates payment links or orders**.
3. The Policy Agent **never mutates merchant database state**.
4. The Policy Agent **never calculates final payable money** (deterministic code evaluates exact paise economics).

---

## 3. Data Flow Assumptions

```text
Buyer Request ──> Buyer Intent Engine (Phase 3) ──> BuyerIntent v1
                                                           │
                                                           ▼
Merchant Catalog ──> Commerce Service (Phase 2) ──> MerchantCommerceContext v1
                                                           │
                                                           ▼
                                               Merchant Policy Agent (Phase 4)
                                                           │
                                                           ▼
                                               Candidate Strategies (2–5)
                                                           │
                                                           ▼
                                               Deterministic Policy Validator
                                                           │
                                                           ▼
                                               Ranked PolicyProposal v1
```

1. **Input Independence**: The Policy Agent consumes `BuyerIntent v1` and `MerchantCommerceContext v1` without requiring raw buyer messages or direct database connections.
2. **Determinism**: Given identical `BuyerIntent` and `MerchantCommerceContext`, the Policy Agent produces identical candidate sets and deterministic economic calculations.
