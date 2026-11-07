# System Architecture Specification

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> **System**: Merchant Policy Agent  
> **Contract Level**: Production Release Candidate (Phase 12.1 Frozen)

---

## 1. Visual System Architecture Diagram

<div align="center">
  <img src="architecture_diagram.svg" alt="System Architecture: Three Decoupled Planes" width="100%" style="border-radius: 12px; border: 1px solid rgba(255,255,255,0.12); margin-bottom: 20px;" />
</div>

> 📄 **Root Specification**: See also root [ARCHITECTURE.md](../ARCHITECTURE.md) for full interactive Mermaid diagrams, 11-stage latency budgets, and security specifications.

## 2. System Architecture Flowchart

```text
       ┌─────────────────────────────────────────────────────────────┐
       │                          AI BUYER                           │
       │  (Autonomous agent with budget, constraints, use case)      │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Natural Language Prompt / API
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                   STAGE 1: BUYER INTENT                     │
       │  IntentExtractor parses category, budget, specs, urgency    │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Structured BuyerIntent
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │               STAGE 2: MERCHANT POLICY AGENT                │
       │  MerchantPolicyAgent reads catalog, unit economics, affinities│
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Generates Candidates
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │              STAGE 3: CANDIDATE STRATEGIES                  │
       │  (Bundle, Bounded Discount, Alternative, Cross-sell, Baseline)│
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Admissibility Filtering
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │             STAGE 4: DETERMINISTIC VALIDATION               │
       │  Margin floor check, discount ceiling check, inventory check│
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Approved Candidates
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                 STAGE 5: POLICY SELECTION                   │
       │  Contextual LinUCB bandit scores UCB = predicted + alpha*std│
       │  Selects Exploit vs. Explore based on uncertainty           │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Chosen Policy Proposal
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                   STAGE 6: FRESH SAFETY                     │
       │  Re-verifies real-time stock & margin floors at execution   │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Authorized Execution Request
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │               STAGE 7: EXECUTION BOUNDARY                   │
       │  Atomically reserves inventory; creates Razorpay Order      │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Order ID & Amount (Paise)
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │              STAGE 8: RAZORPAY TEST MODE                    │
       │  Real test gateway: order creation, payment capture/fail    │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Authorized Payment Webhook
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                   STAGE 9: OUTCOME FEEDBACK                 │
       │  OutcomeFeedbackService resolves transaction state (PAID)   │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Realized Revenue & COGS
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                    STAGE 10: REWARD ENGINE                  │
       │  Reward Formula = Realized Revenue - Realized COGS (Paise)  │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Observed Economic Contribution
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                   STAGE 11: POLICY MEMORY                   │
       │  Stores immutable PolicyMemoryRecord & LearningEvidence     │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Evidence Record
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                 STAGE 12: LinUCB LEARNING                   │
       │  Updates covariance matrix A and feature vector b           │
       └──────────────────────────────┬──────────────────────────────┘
                                      │ Updated Bandit Model
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │              STAGE 13: EXPLORATION / LIFECYCLE              │
       │  Updates exploration budget; evaluates candidate promotion  │
       └──────────────────────────────┬──────────────────────────────┘
                                      ↺ Closed Loop Iteration

       ═══════════════════════════════════════════════════════════════
       GOVERNANCE PLANE: MERCHANT CONTROL CENTER (DASHBOARD)
       ═══════════════════════════════════════════════════════════════
              │ Read-Only Queries
              ▼
       ┌─────────────────────────────────────────────────────────────┐
       │  - Overview Dashboard (`/`): KPIs, Learning Signals         │
       │  - AI Decisions Ledger (`/decisions`): 11-Stage Lineage      │
       │  - Policy Governance (`/policies`): Audit, Promote/Rollback │
       │  - Learning Center (`/learning`): Model Weights, Health     │
       │  - Activity Log (`/activity`): Immutable Audit Stream       │
       └─────────────────────────────────────────────────────────────┘
```

---

## 2. Structural Separation of Planes

The architecture enforces strict separation between the **Execution Plane**, the **Learning Plane**, and the **Governance Plane**:

| Plane | Components | Invariants |
| :--- | :--- | :--- |
| **Execution Plane** | `IntentExtractor`, `MerchantPolicyAgent`, `PolicySafetyValidator`, `DecisionExecutionBoundaryService`, `RazorpayClient` | - Zero floating point math (all values in integer paise)<br>- Real-time inventory reservation<br>- Zero payment processing without prior safety clearance<br>- Idempotent execution requests |
| **Learning Plane** | `OutcomeFeedbackService`, `PolicyMemoryService`, `PolicyLearningModelService` (LinUCB) | - Only processed upon authentic payment state resolution<br>- Zero reward on payment failure or abandonment<br>- Covariance matrix regularized with Ridge parameter $\lambda = 1.0$<br>- Replay-safe outcome processing |
| **Governance Plane** | `PolicyLifecycleService`, `DashboardOverviewService`, `PolicyViewService`, `DecisionViewService` | - Read-only projection from authoritative persistent tables<br>- Candidate policies require explicit evidence criteria before promotion<br>- Manual operator overrides logged as immutable audit events<br>- Baseline fallback always available via single pointer switch |

---

## 3. Strict Boundary Invariants

1. **Learning != Promotion**:
   The LinUCB bandit model continuously learns contextual weights $\theta = A^{-1}b$ from every transaction outcome. However, learning NEVER mutates the governed `active_policy` pointer. Promoting a candidate policy to become the active commercial rule requires meeting formal statistical gating criteria (minimum sample size, positive observed contribution, margin floor adherence).

2. **Prediction != Observation**:
   - `predicted_contribution_paise`: The bandit model's expectation of contribution *before* execution.
   - `observed_contribution_paise`: The actual realized gross contribution *after* payment capture ($Realized Revenue - Realized COGS$).

3. **Execution != Payment**:
   - `EXECUTION_COMPLETED`: An order has been validated and authorized in the execution boundary.
   - `PAYMENT_SUCCESS`: Funds have been captured by Razorpay. An executed order may result in `PAYMENT_FAILED` (e.g. buyer checkout abandonment), which correctly yields ₹0 reward.

4. **Zero Financial Leakage to Buyer View**:
   The public `BuyerOfferView` strictly exposes consumer-facing details (price, discount percentage, category rationale). Internal merchant economics (`cogs_paise`, `gross_margin_percent`, `predicted_contribution_paise`) are strictly confined to `MerchantEvaluationView`.
