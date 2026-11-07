# 🛡️ Verification & Clean-Room Testing Guide

This document describes the testing architecture, reproducibility guarantees, and verification procedures for the **Merchant Policy Agent**.

---

## 📊 Test Suite Status & Coverage

The repository enforces **clean-room reproducibility** with 100% hermetic unit testing.

| Test Suite | File Count | Test Count | Pass Rate | Dependencies / Network |
| :--- | :--- | :--- | :--- | :--- |
| **Unit Test Suite** (`tests/unit/`) | 35 files | **562 tests** | **100% PASS** | Zero network, in-memory SQLite (`:memory:`), fully mocked gateway |
| **Integration Test Suite** (`tests/integration/`) | 29 files | **380 tests** | **100% PASS** | Hermetic test mode database, zero live secrets required |
| **Total Automated Tests** | **64 files** | **942 tests** | **100% PASS** | Execution time: ~2 minutes |

---

## ⚡ Clean-Room Reproduction (Under 60 Seconds)

To reproduce all 942 passing tests from a fresh clone:

```powershell
# 1. Clone repository
git clone https://github.com/dhanusharer/merchant-policy-agent.git
cd merchant-policy-agent

# 2. Set up virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. Copy environment configuration
cp .env.example .env

# 4. Run the hermetic unit tests (562 tests)
pytest tests/unit -v --tb=short

# 5. Run the integration test suite (380 tests)
pytest tests/integration -q

# 6. Run the canonical MCP AI buyer journey demo
python scripts/run_mcp_buyer_demo.py
```

---

## 🔒 Hermeticity Guarantees

1. **No External Network Calls in Unit Tests**: External services like Razorpay's API and Google Gemini are hermetically mocked during test suite execution (`httpx.Client.post` and `RazorpayOrderService.create_order` mocks).
2. **In-Memory Isolated Database**: Unit tests run against isolated in-memory SQLite engines (`sqlite+aiosqlite:///:memory:`). No tests write to or require a pre-existing local disk `./test.db`.
3. **No Flaky Sleep Timers**: All concurrency and state transition tests use deterministic event triggers and async queue waits rather than flaky `time.sleep` calls.
4. **Timezone-Aware UTC Timestamps**: Zero deprecated `datetime.utcnow()` calls. All timestamps across services and tests use explicit timezone-aware `datetime.now(timezone.utc)`.

---

## 🤖 Dual-Engine Policy Verification

The Policy Agent provides dual-engine candidate generation (`services/policy/agent.py` & `services/policy/llm_client.py`):
- **LLM Mode (Google Gemini)**: Formats merchant catalog, inventory, and buyer intent into a strict JSON schema prompt and queries Gemini (`gemini-1.5-flash`).
- **Deterministic Heuristic Fallback**: If `GEMINI_API_KEY` is absent or the API request times out (>3.5s budget), the agent automatically falls back to deterministic heuristic generation (`COMPLEMENTARY_BUNDLE`, `BOUNDED_DISCOUNT`, `SINGLE_PRODUCT`, `NO_OFFER`).
- **Deterministic Validation**: Both LLM-proposed and heuristic candidates are validated against identical deterministic guardrails (margin floors, discount ceilings, real-time inventory).

---

## 🔌 Phase 13: External AI Buyer MCP Test Verification

Phase 13 tests certify the Model Context Protocol interface:
- `tests/unit/test_mcp_tools.py` (9 tests): Hermetic validation of all 6 conceptual MCP tools, input schema constraints, and error mappings.
- `tests/unit/test_mcp_security.py` (7 tests): Adversarial validation of `BuyerResponseFirewall` (zero COGS leakage), cross-tenant isolation, capability guard rejection, replay prevention, and stale TTL locks.
- `tests/integration/test_mcp_end_to_end.py` (3 tests): Full JSON-RPC 2.0 dispatch, SSE streaming endpoint, and lifecycle session orchestration.
- `tests/integration/test_mcp_benchmark.py` (12 tests): Canonical benchmark matrix validating `MCP-01` through `MCP-12` against the 11-stage decision architecture.

Test verification file:
- `tests/unit/test_policy_llm_agent.py` validates prompt structure, structured JSON parsing, dual-engine fallback, and downstream guardrails.

---

## 💳 Live Razorpay Test Mode Verification

To verify real interaction with Razorpay's Test Mode servers:

1. Add your real Razorpay test keys to `.env`:
   ```env
   RAZORPAY_KEY_ID=rzp_test_YourKeyIdHere
   RAZORPAY_KEY_SECRET=YourKeySecretHere
   RAZORPAY_WEBHOOK_SECRET=YourWebhookSecretHere
   ```
2. Run the end-to-end test mode script:
   ```powershell
   python scripts/run_real_testmode_e2e.py
   ```
3. If placeholder keys are detected, the script transparently reports `AWAITING TEST CREDENTIALS` instead of faking live provider success. When valid `rzp_test_` keys are present, it creates an authentic order on `api.razorpay.com/v1/orders` and launches an interactive test card checkout flow.
