# Phase 7 Metrics, Guardrails & Evaluation Classifications

## 1. Primary Commercial Metric

The system's North Star metric is:
> **Contribution per AI Shopper**

### Exact Formulations:
1. **Simulated Stage**:
   $$\text{Expected Contribution per AI Shopper (Paise)} = \frac{\sum \text{Simulated Contribution (Paise)}}{\text{Sample Size (Eligible Decision Instances)}}$$
2. **Verified Test-Mode Stage**:
   $$\text{Observed Contribution per Test-Mode Shopper (Paise)} = \frac{\sum \text{Verified Captured Gross Profit (Paise)}}{\text{Total Verified Shoppers}}$$

---

## 2. Core Secondary Metrics & Allocation Measures

| Metric Name | Numerator | Denominator | Unit | Meaning |
|:---|:---|:---|:---:|:---|
| **Actual Control Count** | Count of decision instances assigned to Control | $N_{\text{ctrl}}$ | Integer | Observed Control arm sample size |
| **Actual Treatment Count** | Count of decision instances assigned to Treatment | $N_{\text{treat}}$ | Integer | Observed Treatment arm sample size |
| **Allocation Ratio** | $N_{\text{treat}}$ | $N_{\text{ctrl}}$ | Ratio Float | Observed allocation balance ($\approx 1.0$) |
| **AI Buyer Selection Rate** | Count of winning variant selections | Total instances assigned to variant | Ratio [0.0, 1.0] | Preference win-rate against alternatives |
| **Order Creation Rate** | Count of Phase 5 orders created | Total instances assigned to variant | Ratio [0.0, 1.0] | Execution gateway passage rate |
| **Payment Success Rate** | Count of captured payments (`payment.captured`) | Total orders created | Ratio [0.0, 1.0] | Verified payment fulfillment rate |
| **Average Order Value (AOV)** | Total revenue in paise | Total winning selections (or captured) | Integer Paise | Average revenue per converted transaction |
| **Average Margin %** | Sum of margins of winning selections | Total winning selections | Percentage % | Realized gross margin percentage |
| **Policy Violation Count** | Count of guardrail breaches | Total decision instances | Count | Number of constraint safety violations |

---

## 3. Evaluation Classifications: Effect Size, Sample Size & Uncertainty

A naive rule like `INCONCLUSIVE when delta = 0` is statistically unsound because tiny non-zero differences (e.g. 50.0% vs 50.1%) are indistinguishable from sample noise.

The `ExperimentEvaluator` evaluates across four dimensions:
1. **Sample Size ($N$)**: If total samples $< 10$ or either arm is 0 $\to$ `INSUFFICIENT_SAMPLE`.
2. **Guardrails**: If Treatment breaches any merchant guardrail $\to$ `GUARDRAIL_FAILURE` (winner is `CONTROL`).
3. **Effect Size & Minimum Detectable Effect (MDE)**:
   - If $|\Delta_{\text{abs}}| == 0 \to$ `INCONCLUSIVE`.
   - If $|\Delta_{\text{rel}}| < \text{MDE}$ (default: $2.0\%$) $\to$ `INCONCLUSIVE`.
4. **Directional Improvement**:
   - If Treatment outperforms Control by $> \text{MDE} \to$ `TREATMENT`.
   - If Control outperforms Treatment by $> \text{MDE} \to$ `CONTROL`.

### Summary of Result Classifications:
| Classification | Trigger Conditions | Winner |
|:---|:---|:---:|
| **`TREATMENT`** | Treatment exceeds Control by $> \text{MDE}$ on primary metric AND passes all guardrails | `TREATMENT` |
| **`CONTROL`** | Control exceeds Treatment by $> \text{MDE}$, OR Treatment fails any guardrail | `CONTROL` |
| **`INCONCLUSIVE`** | Delta is zero, OR relative effect size $|\Delta_{\text{rel}}| < \text{MDE}$ threshold | `None` |
| **`INSUFFICIENT_SAMPLE`** | Total observations $< 10$ or either arm has 0 observations | `None` |
| **`GUARDRAIL_FAILURE`** | Treatment breaches margin floor, discount ceiling, or inventory constraint | `CONTROL` |

---

## 4. Guardrail Enforcement Logic

```text
Treatment Primary Metric: IMPROVED (+45%)
Margin Guardrail: FAILED (Observed 25% < Floor 40%)

Outcome:
Evidence Status: GUARDRAIL_FAILURE
Winner: CONTROL (Treatment Disqualified)
```

### Supported Guardrails:
- `MIN_MARGIN_PERCENT`: Enforces unit-economic margin floor (e.g. 40%).
- `MAX_DISCOUNT_PERCENT`: Prevents predatory price cuts exceeding merchant bounds.
- `MAX_PRICE_PAISE`: Enforces buyer affordability ceiling.
- `INVENTORY_SAFETY`: Disqualifies variants that induce stockouts.

---

## 5. Expected vs. Observed Economics Separation

$$\text{Policy Expected Economics} \ne \text{Simulated Buyer Selection} \ne \text{Observed Test-Mode Transaction} \ne \text{Production Commercial Outcome}$$

- **Simulated Outcomes**: Represent simulated AI buyer selection under Phase 6. Contribution is model-estimated.
- **Observed Test-Mode Outcomes**: Represent real Razorpay Test-Mode order creation and webhook reconciliation.
- **Production Outcomes**: Real human customer transactions (not available in this test-mode buildathon track).
