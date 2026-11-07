# Demo Presentation Script & Speaking Flow

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> **Format**: 5-Minute Video Walkthrough + Technical Depth Addendum  
> 🎥 **Official Submission Video Recording**:  
> **[Watch the Demo Video on Google Drive](https://drive.google.com/drive/folders/1t1ntVPLLywJ2RIn9y9WB9vKAlRPnbtA1?usp=drive_link)**  
> *Google Drive Folder Link*: `https://drive.google.com/drive/folders/1t1ntVPLLywJ2RIn9y9WB9vKAlRPnbtA1?usp=drive_link`

---

## 5-Minute Spoken Presentation Script

### ACT 1 — THE TENSION (0:00 – 0:25)
- **Visual**: Show traditional web storefront vs. a terminal/API interface showing programmatic AI buyer queries.
- **Narrator**:
  > "When an AI becomes the buyer, products stop being enough.
  > If three different merchants can satisfy the exact same buyer prompt with good backpacks, what makes the AI choose one merchant over another?
  > It cannot just be search keywords or storefront photos. It comes down to commercial terms: pricing, bundles, guarantees, delivery speed, and inventory confidence.
  > [PAUSE]
  > The question every business will face is: *What makes this merchant worth choosing?*"

---

### ACT 2 — THE PRODUCT (0:25 – 0:50)
- **Visual**: Show the Architecture Invariant diagram:
  `LLM Proposes ➔ Code Validates ➔ Code Executes ➔ Razorpay Reports ➔ Agent Learns`
- **Narrator**:
  > "We built the **Merchant Policy Agent**.
  > It is not a shopping chatbot. It is not an AI recommendation widget.
  > It is a policy runtime that learns merchant-specific commercial strategies to maximize profitable revenue while strictly respecting business constraints.
  > In simple terms: it understands buyer intent, decides the most competitive commercial offer, and learns from verified transaction outcomes."

---

### ACT 3 — THE TRUST BOUNDARY (0:50 – 1:15)
- **Visual**: Highlight the Execution Boundary & Safety Filter contracts.
- **Narrator**:
  > "Here is the engineering reality: if you let an LLM directly set prices, issue discounts, or create orders, it will hallucinate margins into the ground.
  > Our foundational architectural rule is simple:
  > [PAUSE]
  > **The LLM can propose. It cannot spend.**
  > More precisely: *The LLM proposes. Code validates. Code executes. Razorpay reports. The agent learns.*
  > The model can propose strategies like a single product, a complementary bundle, or even no offer. But deterministic code owns margin floors, discount ceilings, inventory locks, staleness checks, and payment authorization."

---

### ACT 4 — LIVE PROOF (1:15 – 2:45)
- **Visual**: Switch to **AI Decisions Ledger** (`http://localhost:3000/decisions`). Open the top unexecuted decision drawer (`dec_20bfb8ca2e85`). Click **"Open Test Checkout"** and complete payment in the authentic Razorpay Test Mode popup.
- **Narrator**:
  > "Let us see it live. This is the Merchant AI Control Center for our demo business, Atlas Travel Gear.
  > A buyer agent submitted a prompt: *'High quality travel backpack for weekend travel under 7500.'*
  > Here is the decision drawer. Look at what happened before any human touched this:
  > 1. The system extracted buyer intent and context.
  > 2. The model proposed a candidate offer: the Atlas All-Weather Backpack at ₹2,999.
  > 3. Our LinUCB contextual bandit evaluated expected contribution.
  > 4. Deterministic code ran a fresh safety check. The margin floor is respected. Inventory is confirmed. The status is **ADMISSIBLE**.
  > Notice this button: **'Open Test Checkout'**.
  > This button only exists because this decision is fresh, admissible, and authorized. If the model had proposed an unsafe discount, or if inventory had run out, the execution boundary would have rejected it, and this button would not exist.
  > [Action: Click 'Open Test Checkout' -> Razorpay Test Mode popup opens]
  > Watch what just happened. The frontend did not mock an order. It called our execution boundary. The boundary atomically locked inventory and created an authentic Razorpay Test Mode order.
  > Now Razorpay Test Mode takes over. The AI did not touch the payment layer. Razorpay handles checkout.
  > [Action: Complete simulated payment in Razorpay modal]"

---

### ACT 5 — WHY THIS IS DIFFERENT (2:45 – 4:10)
- **Visual**: Show the auto-refreshed Decision Drawer displaying all 11 stages active. Then switch to **Policies** (`http://localhost:3000/policies`).
- **Narrator**:
  > "The payment completed in Razorpay Test Mode. The webhook was verified with HMAC-SHA256.
  > Look at the complete 11-stage identity chain:
  > **Request ➔ Opportunity ➔ Decision ➔ Authorization ➔ Execution ➔ Order ➔ Payment ➔ Outcome ➔ Evidence ➔ Memory ➔ Model Update.**
  > Every link is an immutable, auditable database record.
  > This brings us to the core distinction:
  > A prediction is not an outcome. A simulation is not a transaction. Only a verified transaction outcome becomes learning evidence.
  > When this payment succeeded, our outcome service computed the realized gross contribution, stored it in policy memory, and updated the LinUCB model parameters.
  > Now look at the Policies tab. Even though the model learned from that transaction, notice that the active policy did NOT silently change.
  > Policy promotion is governed. A candidate policy only graduates to active when it passes statutory safety checks and satisfies sample-size evidence criteria. The merchant stays in control."

---

### ACT 6 — WE TRIED TO BREAK IT (4:10 – 4:35)
- **Visual**: Show the validation and benchmark documentation badges (919 tests, 31 adversarial scenarios).
- **Narrator**:
  > "Because this handles commercial transactions, we spent as much time trying to break it as building it.
  > We built a benchmark suite of 31 adversarial scenarios and ran 919 automated regression tests covering:
  > - decisions past their 15-minute freshness TTL,
  > - duplicate webhook replays,
  > - payment failures resulting in zero reward,
  > - cross-tenant access attempts,
  > - and concurrent inventory exhaustion.
  > Every single test enforces that the execution boundary never leaks money or crosses tenant borders."

---

### ACT 7 — FINAL MESSAGE (4:35 – 5:00)
- **Visual**: Return to the **Overview Dashboard** (`http://localhost:3000`).
- **Narrator**:
  > "Today, merchants spend billions optimizing websites for human eyes.
  > [PAUSE]
  > As AI becomes the buyer, merchants will not be optimizing storefront pixels. They will be optimizing commercial policies for autonomous decision engines.
  > That is what we built: a system that protects the merchant's bottom line while teaching an AI why this business is worth choosing.
  > Thank you."

---

### 3-Line Judge Memory Test
1. **The Core Rule**: The LLM proposes commercial strategies, but deterministic code validates margins, locks inventory, and authorizes execution.
2. **The Truth Layer**: Razorpay Test Mode provides the tamper-proof transaction truth that feeds the closed-loop learning model.
3. **The Commercial Vision**: As AI becomes the buyer, merchants will compete on intelligent, governed commercial policies rather than human storefront layouts.

---

## ACT 6 — VYAPAR MITRA: GNANI AI VOICE ADVISOR (4:10 – 5:00)
- **Visual**: Navigate to **AI Voice Doctor** (`http://localhost:3000/doctor`). Click the pulsing circular microphone button and speak in Kannada or English.
- **Narrator**:
  > "For India's retail merchants, typing complex queries into dashboards is unrealistic when managing customers in the store.
  > This is **Vyapar Mitra's AI Voice Doctor**, powered directly by **Gnani AI's Prisma STT and Timbre TTS**.
  > Let's test it live with our demo merchant, **Vastram**."
- **Demonstration 1 (Kannada Code-Mixed / Kanglish)**:
  - **Speaker (Microphone)**: *"Ivattu sales eshtu?"* (What are today's sales?)
  - **Prisma STT**: Live audio transcribes in 240ms with `indic-auto` language detection.
  - **Intelligence Engine**: Reconciles exactly 18 orders totaling ₹44,982.00 today across WhatsApp, D2C, and Amazon.
  - **Timbre TTS (Voice: Lakshmi)**: Synthesizes crystal-clear audio: *"ಇವತ್ತು ಒಟ್ಟು 18 ಆರ್ಡರ್‌ಗಳಿಂದ ₹44,982 ಮಾರಾಟವಾಗಿದೆ. ವಾಟ್ಸಾಪ್ ನೇರ ಚಾನೆಲ್‌ನಲ್ಲಿ 64.2% ನಷ್ಟು ಅತ್ಯುತ್ತಮ ಮಾರ್ಜಿನ್ ದಾಖಲಾಗಿದೆ."*
  - **Audio Player**: Audio automatically streams and plays directly in the browser.
- **Demonstration 2 (Dead Stock & Reorder Alert)**:
  - **Speaker (Microphone)**: *"Which products are moving slowly and what should I reorder?"*
  - **Doctor Advisor**: Pinpoints 3 dead stock SKUs trapped in inventory for >60 days and flags Handloom Silk Sarees needing urgent reorder.
  - **Action Governance Card**: Proposes a flash discount with a 25.00% gross margin floor check. Merchant clicks **'Approve & Execute Action'** to write back to the store without hallucination.
- **Demonstration 3 (Request a Telephony Callback)**:
  - Merchant clicks **'Schedule Voice Briefing'** to register a phone callback for automated daily morning performance reports.

---

## Technical Walkthrough Addendum (For Deep-Dive Evaluation)

If technical evaluators require an extended 10-minute code walkthrough:

1. **Unit Economics & Commerce Primitives**:
   - Inspect `domain/models.py` (`Merchant`, `Product`, `ProductAffinity`).
   - Demonstrate that integer paise arithmetic prevents floating-point rounding errors.
2. **Intent & Candidate Generation**:
   - Inspect `services/intent/extractor.py` and `services/agent/policy_agent.py`.
   - Show how candidate generation creates typed `PolicyProposal` instances.
3. **Execution Gate & Razorpay Client**:
   - Inspect `services/boundary/service.py` and `services/razorpay/client.py`.
   - Show how orders are created via the official Razorpay test credentials.
4. **Bandit Learning Math**:
   - Inspect `services/learning/model_service.py` and `services/learning/schemas.py`.
   - Show the LinUCB ridge regression matrix update: $A \leftarrow A + x x^T$ and $b \leftarrow b + r x$.
5. **Multi-Tenant Isolation**:
   - Show cross-tenant query rejection between `merch_atlas_travel` and `merch_alpha`.
