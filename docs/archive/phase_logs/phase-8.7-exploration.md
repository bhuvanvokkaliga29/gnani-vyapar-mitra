# Phase 8.7 & 8.7.1 Technical Specification: Constrained Exploration / Exploitation Engine

**Contract Version**: `policy-exploration/v1` (Hardened)  
**Status**: **COMPLETE, VERIFIED, ADVERSARIALLY HARDENED, CONTRACT FROZEN**  
**Core Invariant**: **BUDGETED UNCERTAINTY-AWARE SELECTION; 100% DETERMINISTIC; EXACT DOWNSIDE EXPOSURE; ATOMIC CONSUMPTION TIMING; CANONICAL UTC DAILY WINDOWS; EVERY PROPOSAL MUST PASS PHASE 8.6; ZERO AUTONOMOUS EXECUTION; ZERO POLICY MUTATION**

---

## 1. Objective & Core Principle

Phase 8.7 establishes the first explicit, bounded **exploration / exploitation decision engine**:
> **`policy-exploration/v1`**

It answers the core operational question:
$$\boxed{\text{"Should the system exploit the current learned preference or deliberately explore a different admissible candidate to reduce uncertainty and improve future merchant-specific learning?"}}$$

### Core Principles:
- **Exploitation Path**: Strictly preserves the Phase 8.5 chosen candidate without altering ranking or injecting exploration pressure.
- **Exploration Path**: Selects an uncertainty-aware candidate ($UCB = \text{pred} + \alpha \cdot \sigma$) from valid alternatives in the Phase 8.5 slate only when exploration is enabled, within budget, and justified by uncertainty.
- **Exploration $\subset$ Admissible Policies**: Every resulting proposal (exploit or explore) must pass the Phase 8.6 deterministic safety gate before being emitted.
- **Zero Randomness**: 100% deterministic, audit-traceable, and reproducible across runs.

---

## 2. Exploitation Semantics

When the engine decides to **exploit**:
- The policy chosen by Phase 8.5 (`selected_policy_id`) is selected directly.
- UCB and uncertainty do **not** influence or alter the selection.
- Reason codes reflect why exploitation occurred (e.g., `EXPLOIT_DEFAULT`, `EXPLOIT_DISABLED`, `EXPLOIT_BUDGET_EXHAUSTED`, `EXPLOIT_CONSECUTIVE_LIMIT_REACHED`, `EXPLOIT_TRIGGER_NOT_SATISFIED`, or `EXPLOIT_FALLBACK_EXPLORATION_UNSAFE`).
- The chosen policy is validated via Phase 8.6 before output.
- Downside exposure consumed is strictly 0 paise.

---

## 3. Exploration Semantics & Economic Eligibility (Phase 8.7.1)

When the engine decides to **explore**:
1. Candidates are filtered from the Phase 8.5 slate, strictly excluding:
   - The current exploit candidate (cannot explore the exploit policy itself).
   - The canonical `NO_OFFER` baseline (reserve baseline is not an exploratory product offer).
   - Candidates that failed structural validity or hit their per-policy exposure cap.
   - Candidates that breach the per-decision exposure cap or total remaining budget.
2. Exploratory scoring:
   $$UCB = \text{predicted\_contribution\_paise} + \text{round}(\alpha_{\text{paise}} \times \sigma)$$
3. **Hardened Trigger Evaluation**:
   - **Trigger A: Uncertainty Advantage Trigger**:
     * Alternative candidate uncertainty $\sigma - \sigma_{\text{exploit}} \ge \tau_{\text{unc}}$ (default $\tau_{\text{unc}} = 0.20$).
     * Optimistic viability: $UCB \ge \text{baseline\_predicted\_contribution\_paise}$.
   - **Trigger B: Under-Observed Policy Trigger (Economic Eligibility)**:
     * Historical observation count $N < N_{\min}$ (default $N_{\min} = 5$).
     * **Optimistic Viability**: $UCB \ge \text{baseline\_predicted\_contribution\_paise}$.
     * **Bounded Deficit**: $\text{predicted} \ge \text{baseline} - \text{max\_underobserved\_deficit\_paise}$ (default: ₹1,000 / 100,000 paise).
     * **Per-Decision Downside Cap**: $\text{exposure\_paise} \le \text{max\_exposure\_per\_decision\_paise}$.
4. Ranking among triggered candidates:
   $$UCB \text{ DESC} \to \sigma \text{ DESC} \to \text{strategy\_priority DESC} \to \text{policy\_id ASC} \to \text{policy\_version ASC}$$
5. Top candidate is sent to Phase 8.6 safety gate.
6. If Phase 8.6 approves (`ADMISSIBLE`):
   - Exploration is confirmed.
   - Budget counters are atomically committed (`opportunities_used += 1`, `exposure_paise_used += exposure_paise`, `consecutive_explorations += 1`).
   - Decision mode is `EXPLORE`.
7. If Phase 8.6 rejects (`REJECTED`):
   - Exploration is aborted.
   - **Zero exposure is consumed**.
   - Deterministic safety fallback to `exploit_candidate` executes.

---

## 4. Role of UCB (Upper Confidence Bound)

- In Phase 8.5: UCB was strictly **excluded** from candidate selection.
- In Phase 8.7: UCB is permitted **exclusively** for exploratory candidate ranking among alternative candidates when exploration is triggered.
- Universal `argmax(UCB)` is prohibited.
- UCB is never claimed to be causal or a calibrated probability.

---

## 5. Exact Downside Economic Exposure Formula (Phase 8.7.1)

Let $\text{benchmark\_contribution} = \max\Big(\text{predicted\_contribution}(\text{exploit}), \; \text{predicted\_contribution}(\text{NO\_OFFER})\Big)$.

The exact pre-decision economic exposure consumed for exploring candidate $C$ is:
$$\boxed{\text{exploration\_exposure\_paise} = \max\Big(0, \; \text{benchmark\_contribution} - \text{predicted\_contribution}(C)\Big)}$$

- Exploit = +₹500, Explore = +₹450 $\to$ Exposure = ₹50 (5,000 paise).
- Exploit = +₹500, Explore = +₹550 $\to$ Exposure = 0 paise.
- Exploit = 0 (NO_OFFER), Explore = -₹100 $\to$ Exposure = ₹100 (10,000 paise).
- Exploit = +₹500, Explore = -₹200 $\to$ Exposure = ₹700 (70,000 paise).

Exploration exposure is a bounded pre-decision risk-control quantity, **NOT** a realized reward, loss, or revenue.

---

## 6. Bounded Risk & Exposure Controls

Merchant-configurable constraints via `MerchantExplorationConfig`:
1. **Opportunity Budget (`max_exploration_opportunities`)**: Maximum exploratory decisions allowed in a window (default: 20).
2. **Consecutive Exploration Limit (`max_consecutive_explorations`)**: Maximum sequential explorations before a mandatory return to exploitation (default: 3).
3. **Policy Exposure Limit (`max_policy_exploration_count`)**: Maximum times a single policy can be chosen via exploration (default: 5).
4. **Context Exposure Limit (`max_context_exploration_count`)**: Maximum explorations permitted within a single buyer context class (default: 10).
5. **Per-Decision Exposure Cap (`max_exposure_per_decision_paise`)**: Maximum exposure permitted for a single decision (default: ₹1,500 / 150,000 paise).
6. **Cumulative Economic Exposure Budget (`max_exposure_paise`)**: Maximum cumulative potential contribution gap attributable to exploration (default: ₹5,000 / 500,000 paise).

---

## 7. Safety Integration & Fallback Behavior

```text
Phase 8.5 Slate
       ↓
8.7 Engine selects exploratory candidate
       ↓
Phase 8.6 Safety Gate
 ├── ADMISSIBLE ──> Confirm EXPLORE, atomically commit exact exposure paise, return proposal
 └── REJECTED   ──> ABORT exploration, commit 0 exposure,
                    fallback to Phase 8.5 exploit candidate,
                    validate exploit candidate via Phase 8.6,
                    return EXPLOIT (reason: EXPLOIT_FALLBACK_EXPLORATION_UNSAFE)
```

---

## 8. Canonical UTC Exploration Windows & Reset Semantics (Phase 8.7.1)

- **Window Format**: `win_YYYY-MM-DD` resolved from UTC timestamp.
- **Boundaries**: Starts `00:00:00.000000 UTC` and ends `23:59:59.999999 UTC`.
- **Reset**: When UTC date rolls, a new row is initialized in `merchant_exploration_states`, cleanly starting operational counters at 0 without mutating old records.
- **Forensic Audit Snapshots**: Each decision persists `budget_state_json` containing before and after counters:
  `opportunities_used_before`, `opportunities_used_after`, `exposure_paise_used_before`, `exposure_paise_used_after`, `consecutive_explorations_before`, `consecutive_explorations_after`, and `config_version`.

---

## 9. Boundary & Non-Goals

- **NO** autonomous transaction execution (owned by Phase 5).
- **NO** Razorpay API calls or payment capture (owned by Phase 1 / Phase 5).
- **NO** inventory reservation (owned by Phase 5).
- **NO** policy promotion or mutation (deferred to Phase 8.8).
- **NO** n8n dependency.
- **NO** stochastic sampling or randomness.
