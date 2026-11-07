# Phase 1: Architectural Findings & Contradictions Registry

This document records any verified contradictions between the Phase 0 architecture and real-world Phase 1 implementation.

---

## 1. Architectural Consistency Audit

- **Razorpay Orders API**: Behavior matches Phase 0 specifications (`POST /v1/orders` requiring `amount` in integer paise, `currency`, optional `receipt` $\le 40$ chars).
- **HMAC Verification**: Raw body hashing matches Razorpay's exact `X-Razorpay-Signature` algorithm.
- **Deduplication**: `X-Razorpay-Event-Id` provides unique transaction identification as planned.
- **Money Handling**: Integer minor units (paise) strictly enforced throughout.

---

## 2. Findings Log

```text
No architectural contradictions discovered during Phase 1.
```
