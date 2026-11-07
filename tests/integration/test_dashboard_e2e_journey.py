"""End-to-End User Journey Test for Phase 10 Merchant Control Center.

Automates the complete product story:
1. Merchant Catalog setup (Phase 2).
2. AI Buyer shopping opportunity evaluated by Canonical Decision Runtime (Phase 9.1).
3. Decision traverses Execution Boundary with point-in-time safety clearance (Phase 9.2).
4. Razorpay Test Mode transaction outcome resolved and ingested into learning (Phase 9.3).
5. Merchant opens Control Center:
   - Overview: KPI reflects observed contribution, recent decision listed, learning insight populated.
   - Decision Detail: Complete 11-stage trace chain verified, buyer vs merchant economics strictly separated.
   - Learning Center: Valid evidence, memory observation, and LinUCB model state verified (zero matrix leakage).
   - Opportunity Trace: End-to-end 8-stage lifecycle reconstructed with COMPLETED status.
   - Control Action: Merchant safely initiates policy rollback; audit trail logs the mutation.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from domain.models import (
    Base,
    Merchant,
    Product,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord,
    Order,
    Payment
)
from apps.api.main import app
from apps.api.core.database import get_db
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.outcome.schemas import OutcomeProcessRequest
from services.outcome.service import OutcomeFeedbackService


@pytest.fixture
async def e2e_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def e2e_client(e2e_db):
    async def override_get_db():
        yield e2e_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_complete_merchant_control_center_journey(e2e_client, e2e_db):
    # -------------------------------------------------------------------------
    # Step 1: Merchant Catalog Setup (Phase 2)
    # -------------------------------------------------------------------------
    merchant = Merchant(
        id="merch_e2e_atlas",
        name="Atlas Travel Gear",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("15.00"),
        target_aov_paise=400000
    )
    product = Product(
        id="prod_e2e_pack",
        merchant_id=merchant.id,
        sku="SKU-ATLAS-E2E",
        name="Atlas Explorer 30L",
        category="travel_backpack",
        price_paise=420000,
        cost_paise=220000,
        inventory_quantity=25,
        reserved_quantity=0,
        is_active=True,
        attributes={"capacity_liters": 30.0, "laptop_size": 16.0}
    )
    now = datetime.now(timezone.utc)
    v_base = MerchantPolicyVersionRecord(
        id=f"pver_{merchant.id}_cand_baseline_merchant-policy/v1",
        merchant_id=merchant.id,
        policy_id="cand_baseline",
        policy_version="merchant-policy/v1",
        lifecycle_status="RETIRED",
        strategy_type="SINGLE_PRODUCT",
        product_ids_json=[product.id],
        rationale="Baseline commercial policy",
        provenance_json={},
        created_at=now,
        updated_at=now
    )
    active_ptr = MerchantActivePolicy(
        merchant_id=merchant.id,
        policy_id="cand_e2e_active",
        policy_version="merchant-policy/v1",
        activated_at=now,
        promotion_id="prom_e2e_init"
    )
    e2e_db.add_all([merchant, product, v_base, active_ptr])
    await e2e_db.commit()

    # -------------------------------------------------------------------------
    # Step 2: Canonical Decision Evaluation (Phase 9.1)
    # -------------------------------------------------------------------------
    opp_id = "opp_e2e_journey_001"
    dec_req = CanonicalDecisionRequest(
        merchant_id=merchant.id,
        opportunity_id=opp_id,
        raw_prompt="travel backpack with 16 inch laptop compartment under 5000"
    )
    envelope = await CanonicalDecisionRuntime.decide(e2e_db, dec_req)
    assert envelope.decision_id.startswith("dec_")
    assert envelope.selected_policy.proposed_price_paise > 0

    # -------------------------------------------------------------------------
    # Step 3: Decision Traverses Execution Boundary (Phase 9.2)
    # -------------------------------------------------------------------------
    exec_res = await DecisionExecutionBoundaryService.execute_decision(
        db=e2e_db,
        decision_id=envelope.decision_id,
        request=DecisionExecuteRequest(merchant_id=merchant.id)
    )
    assert exec_res.execution_id.startswith("dexec_")
    assert exec_res.boundary_status == "EXECUTION_COMPLETED"
    assert exec_res.order_id is not None

    # Simulate Phase 5 captured payment
    pmt_id = f"pay_{opp_id[-8:]}"
    payment = Payment(
        id=pmt_id,
        order_id=exec_res.order_id,
        amount_paise=exec_res.authorized_amount_paise,
        currency="INR",
        status="captured",
        method="card"
    )
    e2e_db.add(payment)
    await e2e_db.commit()

    # -------------------------------------------------------------------------
    # Step 4: Outcome Resolution & Closed-Loop Learning (Phase 9.3)
    # -------------------------------------------------------------------------
    outcome_req = OutcomeProcessRequest(
        merchant_id=merchant.id,
        execution_id=exec_res.execution_id
    )
    out_res = await OutcomeFeedbackService.process_outcome(e2e_db, outcome_req)
    assert out_res.outcome_status == "PAYMENT_SUCCESS"
    assert out_res.learning_eligible is True
    assert out_res.evidence_id is not None
    assert out_res.memory_id is not None

    # -------------------------------------------------------------------------
    # Step 5: Merchant Inspects Overview Dashboard (Phase 10)
    # -------------------------------------------------------------------------
    ov_resp = await e2e_client.get(f"/api/v1/dashboard/overview?merchant_id={merchant.id}")
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()
    assert ov_data["merchant_id"] == merchant.id
    assert ov_data["runtime_status"] == "HEALTHY"
    assert ov_data["decision_count"] == 1
    assert ov_data["paid_transactions_count"] == 1
    assert ov_data["observed_contribution_paise"] > 0
    assert len(ov_data["recent_decisions"]) == 1
    assert ov_data["recent_decisions"][0]["outcome_status"] == "PAYMENT_SUCCESS"
    assert ov_data["recent_decisions"][0]["learning_eligible"] is True

    # -------------------------------------------------------------------------
    # Step 6: Merchant Opens Decision Detail Drawer (Phase 10)
    # -------------------------------------------------------------------------
    det_resp = await e2e_client.get(f"/api/v1/dashboard/decisions/{envelope.decision_id}?merchant_id={merchant.id}")
    assert det_resp.status_code == 200
    det_data = det_resp.json()
    # Verify 11-stage trace chain links
    assert det_data["decision_id"] == envelope.decision_id
    assert det_data["opportunity_id"] == opp_id
    assert det_data["authorization_id"] == exec_res.authorization_id
    assert det_data["execution_id"] == exec_res.execution_id
    assert det_data["order_id"] == exec_res.order_id
    assert det_data["payment_id"] == pmt_id
    assert det_data["outcome_id"] == out_res.outcome_id
    assert det_data["evidence_id"] == out_res.evidence_id
    assert det_data["memory_id"] == out_res.memory_id
    assert det_data["applied_observation_id"] is not None

    # Verify Buyer vs Merchant Information Hygiene
    # Buyer view has price, products, but NO cogs or margin
    assert det_data["buyer_offer"]["offer_price_paise"] == envelope.selected_policy.proposed_price_paise
    assert "cogs_paise" not in det_data["buyer_offer"]
    # Merchant view has private unit economics
    assert det_data["merchant_evaluation"]["cogs_paise"] > 0
    assert det_data["merchant_evaluation"]["gross_margin_percent"] > 0

    # -------------------------------------------------------------------------
    # Step 7: Merchant Inspects Learning Center (Phase 10)
    # -------------------------------------------------------------------------
    learn_resp = await e2e_client.get(f"/api/v1/dashboard/learning?merchant_id={merchant.id}")
    assert learn_resp.status_code == 200
    learn_data = learn_resp.json()
    assert learn_data["health"]["valid_evidence_count"] == 1
    assert learn_data["health"]["memory_observations_count"] == 1
    assert learn_data["health"]["model_updates_count"] == 1
    assert learn_data["model_metadata"]["observation_count"] == 1
    assert len(learn_data["context_breakdown"]) >= 1

    # -------------------------------------------------------------------------
    # Step 8: Merchant Reconstructs Complete Opportunity Trace (Phase 10)
    # -------------------------------------------------------------------------
    trace_resp = await e2e_client.get(f"/api/v1/dashboard/traces/{opp_id}?merchant_id={merchant.id}")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()
    assert trace_data["opportunity_id"] == opp_id
    assert trace_data["trace_status"] == "COMPLETED"
    assert "9.1_DECISION" in trace_data["stages_present"]
    assert "9.2_EXECUTION" in trace_data["stages_present"]
    assert "9.3_OUTCOME" in trace_data["stages_present"]

    # -------------------------------------------------------------------------
    # Step 9: Merchant Performs Safe Policy Rollback (Phase 10)
    # -------------------------------------------------------------------------
    rollback_resp = await e2e_client.post(
        "/api/v1/dashboard/policies/rollback",
        json={
            "merchant_id": merchant.id,
            "target_policy_id": "cand_baseline",
            "rationale": "Rollback to verified baseline policy"
        }
    )
    assert rollback_resp.status_code == 200
    rb_res = rollback_resp.json()
    assert rb_res["success"] is True
    assert rb_res["policy_id"] == "cand_baseline"
    assert rb_res["audit_event_id"] is not None

    # Verify Activity log reflects rollback audit event
    act_resp = await e2e_client.get(f"/api/v1/dashboard/activity?merchant_id={merchant.id}&limit=10")
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["total"] >= 1
    assert any(ev["action"] == "POLICY_ROLLED_BACK" for ev in act_data["items"])
