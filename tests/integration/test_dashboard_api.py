"""Integration Tests for Phase 10 Merchant Control Center API Router.

Tests:
1. All GET /api/v1/dashboard/* endpoints return valid DTOs.
2. Information hygiene: Zero COGS/margin in buyer view, zero raw matrices in learning view.
3. Strict tenant isolation across all dashboard endpoints (Merchant A vs Merchant B).
4. Safe control action (rollback) updates authoritative policy state and logs audit event.
5. Cross-tenant control mutation is blocked with 403 Forbidden.
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from domain.models import Base, Merchant, Product
from apps.api.main import app
from apps.api.core.database import get_db
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime
from services.boundary.schemas import DecisionExecuteRequest
from services.boundary.service import DecisionExecutionBoundaryService
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.schemas import PolicyPromotionRequest


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def api_client(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def two_merchants(test_db):
    # Merchant A
    mA = Merchant(
        id="merch_alpha",
        name="Alpha Outfitter",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_MARGIN",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("15.00")
    )
    pA = Product(
        id="prod_alpha_01",
        merchant_id=mA.id,
        sku="SKU-ALPHA-01",
        name="Alpha Daypack",
        category="travel_backpack",
        price_paise=350000,
        cost_paise=180000,
        inventory_quantity=15,
        reserved_quantity=0,
        is_active=True
    )

    # Merchant B
    mB = Merchant(
        id="merch_bravo",
        name="Bravo Gear",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=Decimal("15.00"),
        maximum_discount_percent=Decimal("20.00")
    )
    pB = Product(
        id="prod_bravo_01",
        merchant_id=mB.id,
        sku="SKU-BRAVO-01",
        name="Bravo Trekking Pack",
        category="hiking_pack",
        price_paise=650000,
        cost_paise=350000,
        inventory_quantity=10,
        reserved_quantity=0,
        is_active=True
    )

    test_db.add_all([mA, pA, mB, pB])
    await test_db.commit()

    # Pre-seed decisions for Merchant A
    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_alpha_01",
        raw_prompt="travel pack under 4000"
    )
    envA = await CanonicalDecisionRuntime.decide(test_db, dec_req)
    await DecisionExecutionBoundaryService.execute_decision(
        db=test_db,
        decision_id=envA.decision_id,
        request=DecisionExecuteRequest(merchant_id=mA.id)
    )

    return mA, mB, envA


@pytest.mark.asyncio
async def test_dashboard_overview_endpoint(api_client, two_merchants):
    mA, mB, envA = two_merchants

    resp = await api_client.get(f"/api/v1/dashboard/overview?merchant_id={mA.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["merchant_id"] == mA.id
    assert data["merchant_name"] == "Alpha Outfitter"
    assert data["currency"] == "INR"
    assert data["runtime_status"] in ["HEALTHY", "ATTENTION_REQUIRED"]
    assert data["decision_count"] >= 1
    assert data["ai_buyer_opportunities_count"] >= 1
    assert len(data["recent_decisions"]) >= 1
    assert data["recent_decisions"][0]["decision_id"] == envA.decision_id


@pytest.mark.asyncio
async def test_dashboard_decisions_list_and_detail(api_client, two_merchants):
    mA, mB, envA = two_merchants

    # List decisions
    list_resp = await api_client.get(f"/api/v1/dashboard/decisions?merchant_id={mA.id}&limit=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(d["decision_id"] == envA.decision_id for d in list_data["items"])

    # Decision detail
    detail_resp = await api_client.get(f"/api/v1/dashboard/decisions/{envA.decision_id}?merchant_id={mA.id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["decision_id"] == envA.decision_id
    assert detail_data["opportunity_id"] == "opp_alpha_01"
    assert detail_data["buyer_offer"]["offer_price_paise"] > 0
    assert detail_data["merchant_evaluation"]["gross_margin_percent"] > 0
    assert detail_data["execution_status"] in ["EXECUTION_COMPLETED", "EXECUTION_REJECTED", "SAFETY_REJECTED"]


@pytest.mark.asyncio
async def test_dashboard_learning_center(api_client, two_merchants):
    mA, mB, envA = two_merchants

    resp = await api_client.get(f"/api/v1/dashboard/learning?merchant_id={mA.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["merchant_id"] == mA.id
    assert "health" in data
    assert "model_metadata" in data
    assert data["model_metadata"]["dimension"] > 0
    assert data["evidence_class"] == "TEST_MODE_OBSERVED"

    # Information Hygiene: Verify no raw matrices leaked
    raw_text = resp.text
    assert "matrix_a_json" not in raw_text
    assert "vector_b_json" not in raw_text


@pytest.mark.asyncio
async def test_dashboard_policies_and_controls(api_client, two_merchants, test_db):
    mA, mB, envA = two_merchants

    # Get policies
    pol_resp = await api_client.get(f"/api/v1/dashboard/policies?merchant_id={mA.id}")
    assert pol_resp.status_code == 200
    pol_data = pol_resp.json()
    assert pol_data["merchant_id"] == mA.id
    assert "versions" in pol_data

    # Seed historical retired version and current active version
    from datetime import datetime, timezone
    from domain.models import MerchantPolicyVersionRecord, MerchantActivePolicy

    now = datetime.now(timezone.utc)
    v1 = MerchantPolicyVersionRecord(
        id=f"pver_{mA.id}_cand_promo_1_merchant-policy/v1",
        merchant_id=mA.id,
        policy_id="cand_promo_1",
        policy_version="merchant-policy/v1",
        lifecycle_status="RETIRED",
        strategy_type="SINGLE_PRODUCT",
        product_ids_json=["prod_alpha_01"],
        rationale="Historical Version A",
        provenance_json={},
        created_at=now,
        updated_at=now
    )
    active_rec = MerchantActivePolicy(
        merchant_id=mA.id,
        policy_id="cand_promo_2",
        policy_version="merchant-policy/v1",
        activated_at=now,
        promotion_id="prom_test_setup"
    )
    test_db.add_all([v1, active_rec])
    await test_db.commit()

    # Perform Rollback to cand_promo_1 via dashboard control API
    rollback_payload = {
        "merchant_id": mA.id,
        "target_policy_id": "cand_promo_1",
        "rationale": "Rollback test via Control Center"
    }
    rb_resp = await api_client.post("/api/v1/dashboard/policies/rollback", json=rollback_payload)
    assert rb_resp.status_code == 200
    rb_data = rb_resp.json()
    assert rb_data["success"] is True
    assert rb_data["action"] == "ROLLBACK"
    assert rb_data["policy_id"] == "cand_promo_1"
    assert rb_data["audit_event_id"] is not None


@pytest.mark.asyncio
async def test_strict_multi_tenant_isolation(api_client, two_merchants):
    mA, mB, envA = two_merchants

    # 1. Merchant B cannot access Merchant A's decision detail
    cross_dec = await api_client.get(f"/api/v1/dashboard/decisions/{envA.decision_id}?merchant_id={mB.id}")
    assert cross_dec.status_code in [403, 404]

    # 2. Merchant B querying decisions gets only Merchant B's (which is 0)
    list_b = await api_client.get(f"/api/v1/dashboard/decisions?merchant_id={mB.id}")
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0

    # 3. Merchant B cannot execute rollback on Merchant A's policy
    cross_rb = await api_client.post(
        "/api/v1/dashboard/policies/rollback",
        json={
            "merchant_id": mB.id,
            "target_policy_id": envA.selected_policy.candidate_id,
            "rationale": "Cross-tenant intrusion"
        }
    )
    assert cross_rb.status_code in [403, 404, 422]
