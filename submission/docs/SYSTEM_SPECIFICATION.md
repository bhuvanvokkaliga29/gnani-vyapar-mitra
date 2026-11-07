# System Specification & Semantic Rules

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> **Component**: Specification of Contracts, Semantics, and Razorpay Integration

---

## 1. Frozen System Contracts

The system enforces 14 versioned contracts across all layers:

1. `buyer-intent/v1`: Schema for extracted intent (category, budget, constraints).
2. `merchant-policy/v1`: Schema for generated candidate commercial policies.
3. `execution-gate/v1`: Schema for safety checks and admission status.
4. `buyer-selection/v1`: Schema for simulated buyer choice and acceptance probability.
5. `policy-experiment/v1`: Schema for controlled A/B and multi-armed bandit experiments.
6. `merchant-learning/v1`: Schema for structured learning evidence.
7. `merchant-reward/v1`: Specification of the gross contribution reward formula.
8. `merchant-memory/v1`: Schema for immutable policy memory records.
9. `learning-algorithm/v1`: Specification of the LinUCB ridge regression algorithm.
10. `feature-schema/v1`: 19-dimensional feature vector specification.
11. `learning-model/v1`: Storage schema for model weights, covariance matrix, and bias.
12. `policy-selection/v1`: Specification of candidate ranking and selection.
13. `policy-safety/v1`: Pre-execution and execution-gate safety checks.
14. `canonical-decision/v1`: Schema for the complete DecisionEnvelope.

---

## 2. The Role of Razorpay in the Closed Loop

Razorpay serves as the **financial truth engine** of the Merchant Policy Agent:

1. **Order Creation Authority**:
   - An authorized decision generates a real Razorpay Order via `RazorpayClient.create_order`.
   - Order amount is strictly an integer in paise.
   - Idempotency is guaranteed through client-provided idempotency keys.

2. **Payment State Resolution**:
   - The agent does NOT assume payment upon order creation (`EXECUTION_COMPLETED != PAYMENT_SUCCESS`).
   - Payment status is authoritatively resolved through Razorpay payment webhooks or test payment capture endpoints (`status: "captured"` vs `status: "failed"`).

3. **Closed-Loop Feedback Trigger**:
   - The authoritative `OutcomeFeedbackService` consumes the verified payment state to calculate the real economic reward.
   - Abandoned checkouts, failed cards, or cancelled UPI payments yield exactly ₹0 reward.

---

## 3. Strict Semantic Distinctions

The Control Center dashboard and API adhere to rigorous semantic invariants:

- **Execution Completed != Payment Success**:
  An order may be created and authorized (execution completed), but the customer may abandon payment at the checkout gateway.
- **Payment Failed != No Execution**:
  A payment failure is an active commercial observation: an order was created, stock was reserved, and the customer refused to complete payment. This provides critical negative signal to the bandit model.
- **Predicted Contribution != Observed Contribution**:
  - Predicted: Model expectation at decision time.
  - Observed: Realized revenue minus realized COGS after payment capture.
- **Ranking Score != Predicted Contribution**:
  The ranking score combines predicted contribution with the LinUCB exploration bonus ($\alpha \cdot \text{uncertainty}$).
- **Learning != Promotion**:
  Model parameter updates occur automatically on every transaction. Policy version promotion to become the merchant's active commercial baseline requires satisfying formal governance criteria.
- **Zero != Missing**:
  A 0% discount is an intentional commercial stance (`NO_OFFER`), not a missing value.
- **N/A != Satisfied**:
  Unchecked criteria are marked pending or not applicable, never assumed to be met.

---

## 4. Key Performance Indicators (KPIs)

- **Conversion Rate**: Percentage of generated offers that convert to paid orders.
- **Gross Contribution (INR)**: Realized revenue minus cost of goods sold.
- **Safety Violation Rate**: Target: 0.00%. Zero orders below minimum gross margin floor.
- **Replay Accuracy**: 100% deterministic reproducibility for historical scenarios.

---

## 5. Gnani AI Multilingual Speech Pipeline Specifications

Vyapar Mitra integrates **Gnani AI** speech technologies into the core conversational workflow:

### 5.1 Gnani Prisma (Speech-to-Text v3.0)
- **Base Endpoint**: `https://api.vachana.ai/stt/v3`
- **Authentication**: `X-API-Key-ID: <GNANI_API_KEY>` (Length: 134 alphanumeric, masked in audit logs)
- **Model**: `prisma-v3.0`
- **Supported Demonstrations**:
  - `indic-auto`: Automatic language and dialect detection.
  - `kn`: Kannada native script (`ಕನ್ನಡ`).
  - `en`: Indian-accented English.
  - Kannada-English Code-Mixed (*Kanglish*): e.g., *"Ivattu sales eshtu?", "Yaava product highest profit ide?"*
- **Audio Specification**: WebM / MP3 / WAV / OGG, 16kHz - 48kHz mono or stereo browser microphone stream.
- **Observed Production Latency**: ~0.24 seconds on test utterances.

### 5.2 Gnani Timbre (Text-to-Speech v3.0)
- **Base Endpoint**: `https://api.vachana.ai/api/v1/tts/inference`
- **Authentication**: `X-API-Key-ID: <GNANI_API_KEY>`
- **Model**: `timbre-v3.0`
- **Verified Production Voices**:
  - `Lakshmi`: High-fidelity female voice, optimized for Kannada and southern Indian phonetics.
  - `Avinash`: Authoritative male voice for executive retail briefings.
  - Other verified accounts: `Shivani, Shubham, Prakash, Pooja, Ananya, Arjun, Rahul, Sneha`.
- **Response Format**: `application/octet-stream` (MPEG 24kHz audio binary).
- **Fallback Engine**: Local edge-tts generator ensures zero-downtime if network connectivity drops.

### 5.3 Business Intelligence & Reasoning Isolation
- **Deterministic Math Engine**: All financial metrics (revenue, COGS, margin percent, dead stock days, reorder thresholds) originate strictly from integer-paise calculations in `BusinessIntelligenceService`.
- **Reasoning Layer**: Google Gemini interprets deterministic summaries; it cannot fabricate or hallucinate sales figures.
- **Auditable Action Proposals**: Merchant recommendations (e.g. stock reorders, flash discounts) require explicit merchant biometric or button approval before write-back to inventory or catalog.

- **AI Buyer Opportunities**: Count of distinct commercial opportunities submitted.
- **Decision Count**: Total canonical decisions evaluated.
- **Decision Rate**: Percentage of opportunities resulting in an evaluated decision (target: 100%).
- **Authorized Executions**: Decisions that passed fresh safety validation and were submitted to the gateway.
- **Paid Transactions**: Authoritatively captured payment transactions in Razorpay Test Mode.
- **Observed Contribution**: Total sum of realized gross margin across paid orders (paise).
- **Expected Contribution**: Total sum of LinUCB predicted contribution across evaluated opportunities (paise).
