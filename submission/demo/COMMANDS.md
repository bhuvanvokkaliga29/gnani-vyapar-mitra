# Verified Execution & Evaluation Commands

> **Razorpay AI Buildathon 2026 — Track 01: AI Growth & Agentic Commerce**  
> All commands listed below have been tested and verified in the evaluation environment.

---

## 1. Environment & Database Initialization

```bash
# 1. Activate Python virtual environment (Windows PowerShell)
.\.venv\Scripts\activate

# 2. Verify dependencies
pip list

# 3. Apply database migrations to current schema head (0db8d2e8f8f1)
alembic upgrade head
```

---

## 2. Deterministic Demo Population & Reset

```bash
# Run the clean-room reset and seed script
# This purges any existing demo state and executes 38 opportunities across 6 context clusters
python scripts/run_demo_population.py
```
*Expected Output*:
- Cleans and seeds `merch_atlas_travel` (Atlas Travel Gear) and `merch_alpha` (Alpha Outfitters)
- Evaluates initial LinUCB model state
- Runs 35 opportunities for Atlas (17 paid transactions, ₹19,529.05 observed contribution)
- Runs 5 opportunities for Alpha (5 paid transactions)
- Replays outcome feedback to prove idempotency
- Blocks cross-tenant outcome replay
- Evaluates candidate policy promotion to verify safe rejection (`INSUFFICIENT_SAMPLE_SIZE`)
- Final status: `Demo population script finished successfully.`

---

## 3. Server Startup

### A. FastAPI Backend Service (Port 8000)
```bash
# In terminal 1: Start Uvicorn API server
uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```
*Health Check*:
```bash
curl -s http://127.0.0.1:8000/health
# Expected: {"status":"ok","timestamp":"...","app":"merchant_policy_agent"}
```

### B. Next.js Control Center Dashboard (Port 3000)
```bash
# In terminal 2: Start Next.js frontend
cd apps/web
npm run dev
```
*Access Points*:
- Overview: `http://localhost:3000`
- AI Decisions: `http://localhost:3000/decisions`
- Policies: `http://localhost:3000/policies`
- Learning: `http://localhost:3000/learning`
- Activity: `http://localhost:3000/activity`

---

## 4. Canonical Demo Execution via API

To execute the canonical hero opportunity on demand via cURL:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runtime/decide \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merch_atlas_travel",
    "request_id": "req_demo_manual_01",
    "opportunity_id": "opp_demo_manual_01",
    "raw_prompt": "I need a travel backpack for a business trip under 8000"
  }'
```

To execute the decision through the execution gate:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/boundary/execute \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merch_atlas_travel",
    "decision_id": "<DECISION_ID_FROM_ABOVE>",
    "idempotency_key": "idem_manual_01"
  }'
```

---

## 5. Automated Verification & Regression Commands

```bash
# 1. Authoritative Parent Unit Suite (541 tests)
pytest tests/unit -q

# 2. Authoritative Parent Integration Suite (364 tests)
pytest tests/integration -q

# 3. Phase 11 Adversarial & Benchmark Suite (49 tests)
pytest tests/integration/test_benchmark_runner.py tests/integration/test_phase11_*.py -q

# 4. Playwright End-to-End Suite (21 tests)
cd apps/web
npx playwright test
```
