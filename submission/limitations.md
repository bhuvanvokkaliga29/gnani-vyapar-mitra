# Known Limitations & Explicit System Boundaries

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> **System**: Merchant Policy Agent  
> **Evaluation Scope**: Hackathon Submission / Technical Review

---

## 1. Razorpay Gateway Scope: Test Mode Only

- The system operates strictly within **Razorpay Test Mode** using sandbox API keys (`rzp_test_...`).
- Real-world production payment gateways involve multi-factor authentication (3D Secure, OTPs), acquirer downtime, network drops, and delayed asynchronous chargebacks. In this implementation, webhook events and payment captures are deterministically verified through simulated test transactions and mock capture flows.
- Production fund settlement, automated merchant bank transfers, and live merchant credentials are not used or supported.

---

## 2. Economic & Reward Formula Scope

- **Gross Contribution Only**:
  The reward formula implemented is frozen strictly as:
  $$\text{Reward (paise)} = \text{Realized Revenue (paise)} - \text{Realized COGS (paise)}$$
- **Excluded Financial Factors**:
  The current implementation does not model:
  - Goods and Services Tax (GST / VAT)
  - Shipping fees and reverse logistics
  - Payment gateway Merchant Discount Rate (MDR)
  - Warehouse handling overheads and operating costs
  - Customer lifetime value (LTV) or repeat-purchase probability

---

## 3. Learning Model Architecture: Contextual Linear Bandit (LinUCB)

- **Linear Assumption**:
  The online learning algorithm utilizes **LinUCB with disjoint ridge regression** ($\lambda = 1.0$). It assumes the expected economic reward is a linear function of the 19-dimensional context-policy feature vector.
- **Non-Linear Buyer Behavior**:
  Real-world buyer preferences often exhibit non-linear interactions, seasonal shifts, and supply-chain shocks that require deep reinforcement learning or non-linear kernel bandits.
- **Cold Start Behavior**:
  In zero-observation states, predicted contribution is strictly ₹0, and exploration is driven entirely by the uncertainty upper confidence bound ($\alpha \cdot \sqrt{x^T A^{-1} x}$).

---

## 4. Merchant Catalog & Buyer Simulation

- **Synthetic Catalog**:
  The products, COGS, inventory quantities, and affinity graphs for demo merchants (`merch_atlas_travel` and `merch_alpha`) are synthetic configurations designed to demonstrate realistic commercial dilemmas (e.g. bundling, stock depletion, margin violation).
- **Controlled Buyer Traffic**:
  The simulated buyer traffic in population runs represents controlled behavioral archetypes (normal backpack seeker, budget sensitive, bundle seeker, checkout abandonment, stock-depletion stress). While diverse, it is a synthetic simulation rather than live consumer traffic.

---

## 5. Production Uplift Claims

- **No Unsubstantiated Uplift Claims**:
  We do not claim a specific percentage revenue or margin uplift in live retail deployments. The demonstrated contribution improvements (e.g. +₹19,529.05 observed contribution over baseline) reflect performance within the controlled benchmark environment and simulation seeds.

---

## 6. Reproducibility Boundaries

- **Supported Environment**:
  The automated test suites (926 tests) and benchmark runners are validated on Windows 11 / Linux with Python 3.11+ and Node.js 20+.
- **Controlled Randomness**:
  While bandit exploration and simulated payment outcomes contain stochastic elements, the demo runner uses fixed context clusters and deterministic seed procedures to guarantee semantically equivalent states across repeated executions.
