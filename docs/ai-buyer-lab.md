# AI Buyer Lab: Synthetic Simulation Environment

This document specifies the design, persona archetypes, simulation protocol, and methodological limitations of the **AI Buyer Lab**.

---

## 1. Purpose of the AI Buyer Lab

The AI Buyer Lab is a controlled testing and benchmarking harness designed to:
1. Stress-test the Merchant Policy Agent against diverse buyer constraint distributions.
2. Evaluate candidate commercial strategies under repeatable, synthetic market conditions.
3. Validate deterministic guardrails against adversarial or extreme buyer constraints.

> [!WARNING]
> **Methodological Boundary**:
> Synthetic buyers are **experimental instruments**, NOT proof of real-world revenue uplift. Results produced in the AI Buyer Lab are tagged `is_simulated = TRUE` and must never be aggregated with verified Razorpay production or test-mode financial metrics.

---

## 2. Standard Buyer Persona Archetypes

The testbed implements six parameterized buyer archetypes:

| Persona Key | Primary Decision Objective | Typical Constraint Profile | Rejection Triggers |
| :--- | :--- | :--- | :--- |
| **`budget_sensitive`** | Minimize total basket expenditure while meeting minimum specs. | Strict budget ceiling (₹5,000–₹12,000); low willingness to pay for accessories. | Price exceeds budget by even 1 paise; expensive add-ons. |
| **`premium`** | Maximize product quality, build materials, and prestige. | High budget headroom (₹25,000–₹60,000); requires top-tier specs and certifications. | Low-tier materials; cheap discounts that degrade perceived quality. |
| **`gift_buyer`** | Convenience, aesthetic presentation, and gift-readiness. | Moderate budget; requires gift packaging, companion consumables, zero hassle. | Unpackaged loose items; missing accessories required for immediate use. |
| **`convenience_sensitive`** | Speed of fulfillment, all-in-one setup, plug-and-play simplicity. | Flexible budget; prioritizes complete turnkey packages and fast shipping guarantees. | Incomplete bundles requiring separate purchases or technical assembly. |
| **`performance_oriented`** | Technical specifications, measurable efficiency, wattage, pressure, durability. | Strict attribute bounds (e.g., $\ge 15$ bar pressure, $\ge 1500$W); high willingness to pay for performance. | Missing technical specs; marketing fluff without quantitative proof. |
| **`bundle_seeker`** | Maximizing perceived value savings through bundled accessory deals. | Seeks multi-item packages where bundle savings exceed 10% of combined list price. | Standalone single-product offers; zero bundle discount incentive. |

---

## 3. Simulation Execution Protocol

```text
                  ┌──────────────────────┐
                  │ Synthetic Persona    │  Generates natural language query
                  │ Generator            │  & structured constraints
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Merchant Policy      │  Extracts intent, evaluates context,
                  │ Agent Pipeline       │  validates guardrails, formulates offer
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Synthetic Buyer      │  Evaluates offer utility function:
                  │ Decision Engine      │  U(strategy) = V(specs) - P(price) + B(bundle)
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼ [ACCEPTED: U > U_min]           ▼ [REJECTED: U ≤ U_min]
       Log Simulated Acceptance          Log Simulated Rejection + Reason
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ Persist Simulation   │  is_simulated = TRUE
                  │ Trace & Metrics      │
                  └──────────────────────┘
```

### 3.1 Decision Utility Function
For a synthetic persona $j$ evaluating candidate strategy $s$:

$$U_j(s) = w_j^{\text{spec}} \cdot \text{SpecMatch}(s) + w_j^{\text{value}} \cdot \text{PerceivedValue}(s) - w_j^{\text{price}} \cdot \left(\frac{\text{Price}(s)}{\text{Budget}_j}\right) + \epsilon$$

Where:
- $\text{SpecMatch}(s) \in [0, 1]$ measures compliance with declared technical constraints.
- $\text{PerceivedValue}(s)$ measures bundle synergy and savings.
- $\epsilon \sim \mathcal{N}(0, \sigma^2)$ represents stochastic noise in buyer decision-making.
- Acceptance condition: $U_j(s) \ge \tau_j$ (persona acceptance threshold).

---

## 4. Methodological Limitations & Documented Biases

1. **Synthetic Persona Bias**: LLM-simulated buyers tend to follow declared constraints more rigidly than human consumers, who frequently exhibit emotional or spontaneous purchasing behavior.
2. **Catalog Familiarity Leakage**: If an LLM buyer agent shares training weights with the merchant agent, it may have latent priors regarding product quality that an external buyer would not possess.
3. **No External Competitive Friction**: In the single-merchant testbed, the buyer evaluates only the host merchant's offer rather than concurrently querying 50 web storefronts.
4. **Zero Financial Risk for Synthetic Agents**: Simulated buyers do not face actual monetary constraints, which can artificially inflate conversion rates for premium bundles unless carefully calibrated.
