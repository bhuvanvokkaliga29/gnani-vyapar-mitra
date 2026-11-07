# Evaluation Strategy & Hackathon Judging Rubric Alignment

This document outlines how the **Merchant Policy Agent** directly addresses every evaluation dimension of the **Razorpay AI Buildathon 2026 (Track 01)**.

---

## 1. Judging Rubric Cross-Reference

| Buildathon Evaluation Dimension | Project Implementation Proof Point | Location in Codebase & Docs |
| :--- | :--- | :--- |
| **1. Problem Taste** *(Real, specific, timely)* | Tackles the inevitable structural shift to AI-mediated commerce. Solves the merchant's margin trap: how to win algorithmic buyer selection without destroying unit economics. | [`docs/problem.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/problem.md)<br>[`docs/verified-assumptions.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/verified-assumptions.md) |
| **2. Product Differentiation** *(Distinct from chatbots, upsell, and SEO)* | Not a buyer chatbot, not an SEO tagger, not a cart checkout wrapper. It is an **autonomous commercial policy learner** that formulates bundles and sets profitable strategies for machine buyers. | [`docs/verified-assumptions.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/verified-assumptions.md)<br>[`docs/mvp.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/mvp.md) |
| **3. Build Quality** *(Reliable, modular, testable)* | Clean modular architecture (FastAPI + Next.js + PostgreSQL). Pydantic v2 schemas, async SQLAlchemy, full type safety, and zero framework bloat. | [`docs/architecture.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/architecture.md)<br>[`docs/technology-decisions.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/technology-decisions.md) |
| **4. AI Judgment** *(AI applied where it creates true value)* | LLM is restricted to qualitative reasoning: semantic intent extraction, creative bundling, and value proposition framing. Math and execution are 100% deterministic. | [`docs/agent-boundary.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/agent-boundary.md)<br>[`docs/agent-state-machine.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/agent-state-machine.md) |
| **5. Financial Safety** *(Bounded, gated, audited actions)* | **The LLM cannot spend.** 5 deterministic gates (margin floor, discount ceiling, buyer budget, inventory, integer math in paise) strictly fence every transaction. | [`docs/economics-model.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/economics-model.md)<br>[`docs/agent-boundary.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/agent-boundary.md) |
| **6. Failure Recovery** *(Graceful handling of real-world failures)* | Explicit handling for 9 failure modes: LLM malformed JSON, downtime, margin violations, gateway timeouts (via API reconciliation), and duplicate webhooks (via `X-Razorpay-Event-Id`). | [`docs/failure-recovery.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/failure-recovery.md)<br>[`docs/failure-testing.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/failure-testing.md) |
| **7. Measurable Impact** *(Empirical uplift & business metrics)* | Evaluates policy performance using the North-Star metric **Expected Contribution per AI Shopper (ECPS)**, along with selection rate, AOV, gross margin, and revenue per shopper. | [`docs/metrics.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/metrics.md)<br>[`docs/experimentation.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/experimentation.md) |
| **8. Razorpay Integration** *(Meaningful architectural role)* | Razorpay is the ground-truth transaction and economic feedback layer. Uses Orders API, authentic test payment capture, and HMAC SHA256 signed webhooks. | [`docs/razorpay-integration.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/razorpay-integration.md)<br>[`docs/problem.md`](file:///c:/Users/DHANUSH%20A%20G/Desktop/razopay_new/docs/problem.md) |

---

## 2. Evaluation Demonstration Script

During the project evaluation and demo walkthrough, the system will demonstrate:
1. **The Static Baseline Flaw (Control)**: Show an AI buyer with budget ₹18,000 searching for a complete espresso setup. The static merchant catalog returns a single machine at ₹15,000, leaving ₹3,000 on the table and missing the grinder requirement.
2. **The Policy Agent Adaptation (Variant B)**: The policy agent parses the intent, formulates a bundle (Machine + Burr Grinder) with a ₹1,000 bundle discount landing at ₹16,000.
3. **Deterministic Guardrail Proof**: Show intentional failure injections (attempting a 40% discount or negative margin) being deterministically halted with zero orders dispatched to Razorpay.
4. **Authentic Razorpay Transaction**: Transition the order to captured state in Razorpay test mode; ingest the HMAC SHA256 webhook; prove event deduplication on re-transmission.
5. **Observed Policy Uplift**: Demonstrate on the dashboard how the realized contribution per shopper updates from ₹75.60 to ₹329.28, shifting the bandit traffic allocation toward the winning policy.
