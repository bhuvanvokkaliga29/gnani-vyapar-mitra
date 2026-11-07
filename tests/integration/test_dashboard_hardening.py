"""Comprehensive Phase 10 Final Hardening Test Suite.

Verifies:
1. Hardening #1 & #31: Tenant authorization boundary across all 10 endpoints.
2. Hardening #7: Stale control action detection and 409 Conflict handling.
3. Hardening #9: Control action idempotency under repeated submission.
4. Hardening #16 & #18: Search and URL parameter tampering defense.
5. Hardening #17: XSS and untrusted text handling without execution.
6. Hardening #19 & #20: Strict secret and model information hygiene.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from domain.models import (
    Base,
    Merchant,
    Product,
    MerchantActivePolicy,
    MerchantPolicyVersionRecord
)
from apps.api.main import app
from apps.api.core.database import get_db
from services.runtime.schemas import CanonicalDecisionRequest
from services.runtime.service import CanonicalDecisionRuntime


@pytest.fixture
async def h_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def h_client(h_db):
    async def override_get_db():
        yield h_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def seed_two_tenants(h_db):
    mA = Merchant(
        id="merch_alpha",
        name="Alpha Goods",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=Decimal("20.00"),
        maximum_discount_percent=Decimal("15.00"),
        target_aov_paise=300000
    )
    mB = Merchant(
        id="merch_beta",
        name="Beta Outfitters",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE",
        minimum_margin_percent=Decimal("15.00"),
        maximum_discount_percent=Decimal("20.00"),
        target_aov_paise=400000
    )
    pA = Product(
        id="prod_alpha",
        merchant_id=mA.id,
        sku="SKU-A",
        name="Alpha Backpack",
        category="travel_backpack",
        price_paise=350000,
        cost_paise=180000,
        inventory_quantity=20,
        reserved_quantity=0,
        is_active=True
    )
    now = datetime.now(timezone.utc)
    vA = MerchantPolicyVersionRecord(
        id="pver_alpha_base",
        merchant_id=mA.id,
        policy_id="pol_alpha_v0",
        policy_version="merchant-policy/v1",
        lifecycle_status="RETIRED",
        strategy_type="SINGLE_PRODUCT",
        product_ids_json=[pA.id],
        rationale="Alpha base",
        provenance_json={},
        created_at=now,
        updated_at=now
    )
    actA = MerchantActivePolicy(
        merchant_id=mA.id,
        policy_id="pol_alpha_v1",
        policy_version="merchant-policy/v1",
        activated_at=now,
        promotion_id="prom_alpha_1"
    )
    h_db.add_all([mA, mB, pA, vA, actA])
    await h_db.commit()

    dec_req = CanonicalDecisionRequest(
        merchant_id=mA.id,
        opportunity_id="opp_alpha_test_01",
        raw_prompt="waterproof backpack"
    )
    envA = await CanonicalDecisionRuntime.decide(h_db, dec_req)
    return mA, mB, envA


# =============================================================================
# 1. HARDENING #1 & #31: TENANT AUTHORIZATION BOUNDARY
# =============================================================================

@pytest.mark.asyncio
async def test_tenant_authorization_intercepts_cross_tenant_header(h_client, seed_two_tenants):
    """Authenticated caller A cannot query or mutate Merchant B under any endpoint."""
    mA, mB, envA = seed_two_tenants

    # Authenticated as Merchant A via X-Caller-Merchant-ID
    caller_a_headers = {"X-Caller-Merchant-ID": mA.id}

    # 1. Overview
    resp = await h_client.get(f"/api/v1/dashboard/overview?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]

    # 2. Decisions List
    resp = await h_client.get(f"/api/v1/dashboard/decisions?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 3. Decision Detail
    resp = await h_client.get(f"/api/v1/dashboard/decisions/{envA.decision_id}?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 4. Policies
    resp = await h_client.get(f"/api/v1/dashboard/policies?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 5. Experiments
    resp = await h_client.get(f"/api/v1/dashboard/experiments?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 6. Learning
    resp = await h_client.get(f"/api/v1/dashboard/learning?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 7. Activity
    resp = await h_client.get(f"/api/v1/dashboard/activity?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 8. Traces
    resp = await h_client.get(f"/api/v1/dashboard/traces/opp_fake?merchant_id={mB.id}", headers=caller_a_headers)
    assert resp.status_code == 403

    # 9. Control: Rollback
    rb_payload = {"merchant_id": mB.id, "target_policy_id": "pol_alpha_v0", "rationale": "Tamper attack"}
    resp = await h_client.post("/api/v1/dashboard/policies/rollback", json=rb_payload, headers=caller_a_headers)
    assert resp.status_code == 403

    # 10. Control: Promote
    pm_payload = {"merchant_id": mB.id, "candidate_policy_id": "pol_alpha_v0", "rationale": "Tamper attack"}
    resp = await h_client.post("/api/v1/dashboard/policies/promote", json=pm_payload, headers=caller_a_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tenant_authorization_with_bearer_token(h_client, seed_two_tenants):
    """Authorization: Bearer <merchant_id> enforces tenant isolation."""
    mA, mB, envA = seed_two_tenants
    bearer_a = {"Authorization": f"Bearer {mA.id}"}

    resp = await h_client.get(f"/api/v1/dashboard/overview?merchant_id={mB.id}", headers=bearer_a)
    assert resp.status_code == 403


# =============================================================================
# 2. HARDENING #7: STALE CONTROL ACTION (OPTIMISTIC CONCURRENCY DEFENSE)
# =============================================================================

@pytest.mark.asyncio
async def test_stale_rollback_rejected_with_409_conflict(h_client, seed_two_tenants, h_db):
    """If another actor promotes a newer policy, stale rollback expecting old active is rejected with 409."""
    mA, mB, envA = seed_two_tenants

    # Current active in database is 'pol_alpha_v1'
    # Simulate stale client expecting 'pol_alpha_stale_v9' as current
    stale_payload = {
        "merchant_id": mA.id,
        "target_policy_id": "pol_alpha_v0",
        "expected_current_policy_id": "pol_alpha_stale_v9",
        "rationale": "Stale client rollback"
    }
    resp = await h_client.post("/api/v1/dashboard/policies/rollback", json=stale_payload)
    assert resp.status_code == 409
    assert "Active policy conflict" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_stale_promotion_rejected_with_409_conflict(h_client, seed_two_tenants):
    """If predecessor active policy mismatches expected, promotion is rejected with 409."""
    mA, mB, envA = seed_two_tenants

    stale_payload = {
        "merchant_id": mA.id,
        "candidate_policy_id": "cand_new_promo",
        "expected_previous_policy_id": "pol_alpha_stale_mismatch",
        "rationale": "Stale client promotion"
    }
    resp = await h_client.post("/api/v1/dashboard/policies/promote", json=stale_payload)
    assert resp.status_code == 409
    assert "Predecessor policy conflict" in resp.json()["detail"]


# =============================================================================
# 3. HARDENING #9: CONTROL ACTION IDEMPOTENCY
# =============================================================================

@pytest.mark.asyncio
async def test_control_action_idempotency_double_rollback(h_client, seed_two_tenants):
    """Repeating the exact same rollback request twice succeeds idempotently without duplicate corruption."""
    mA, mB, envA = seed_two_tenants

    rb_payload = {
        "merchant_id": mA.id,
        "target_policy_id": "pol_alpha_v0",
        "rationale": "First rollback submission"
    }
    # 1. First submission
    resp1 = await h_client.post("/api/v1/dashboard/policies/rollback", json=rb_payload)
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True

    # 2. Second submission (double-click simulation)
    resp2 = await h_client.post("/api/v1/dashboard/policies/rollback", json=rb_payload)
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True
    assert resp2.json()["action"] == "ROLLBACK"


# =============================================================================
# 4. HARDENING #16 & #18: SEARCH & URL TAMPERING
# =============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_url_tampering_rejected(h_client, seed_two_tenants):
    """Merchant B cannot access Merchant A's decision ID even if knowing the exact decision ID."""
    mA, mB, envA = seed_two_tenants

    # Merchant B queries Merchant A's decision_id
    resp = await h_client.get(f"/api/v1/dashboard/decisions/{envA.decision_id}?merchant_id={mB.id}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# =============================================================================
# 5. HARDENING #17: XSS & UNTRUSTED TEXT HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_xss_and_malicious_text_sanitization(h_client, seed_two_tenants):
    """Untrusted text with HTML script tags and injection payloads does not break schemas or execute."""
    mA, mB, envA = seed_two_tenants

    xss_payload = {
        "merchant_id": mA.id,
        "target_policy_id": "pol_alpha_v0",
        "rationale": "<script>alert('pwned')</script> --drop table users; \n\n"
    }
    resp = await h_client.post("/api/v1/dashboard/policies/rollback", json=xss_payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify audit event preserves sanitized string without injection
    act_resp = await h_client.get(f"/api/v1/dashboard/activity?merchant_id={mA.id}&limit=5")
    assert act_resp.status_code == 200
    items = act_resp.json()["items"]
    assert any("<script>" in it["details"].get("reason", "") for it in items)


# =============================================================================
# 6. HARDENING #19 & #20: STRICT SECRET & MODEL INFORMATION HYGIENE
# =============================================================================

@pytest.mark.asyncio
async def test_response_secret_and_model_hygiene(h_client, seed_two_tenants):
    """Dashboard APIs never expose secrets, database credentials, or raw LinUCB matrices."""
    mA, mB, envA = seed_two_tenants

    # 1. Overview
    ov = (await h_client.get(f"/api/v1/dashboard/overview?merchant_id={mA.id}")).json()
    raw_ov_str = str(ov).lower()
    assert "password" not in raw_ov_str
    assert "key_secret" not in raw_ov_str
    assert "client_secret" not in raw_ov_str
    assert "private_key" not in raw_ov_str
    assert "webhook_secret" not in raw_ov_str
    assert "database_url" not in raw_ov_str

    # 2. Decision Detail: Buyer View Hygiene
    det = (await h_client.get(f"/api/v1/dashboard/decisions/{envA.decision_id}?merchant_id={mA.id}")).json()
    assert "cogs_paise" not in det["buyer_offer"]
    assert "gross_margin_percent" not in det["buyer_offer"]

    # 3. Learning Center: Model Matrix Hygiene
    learn = (await h_client.get(f"/api/v1/dashboard/learning?merchant_id={mA.id}")).json()
    assert "a_matrix" not in learn["model_metadata"]
    assert "b_vector" not in learn["model_metadata"]
    assert "theta" not in learn["model_metadata"]
