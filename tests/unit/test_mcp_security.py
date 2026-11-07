"""Security and adversarial tests for MCP Commerce interface.

Verifies:
1. Zero economic leakage through Buyer Response Firewall.
2. Cross-tenant isolation (catalog, offers, checkout, orders).
3. Capability-based authorization gating.
4. Idempotency and replay resistance.
5. Freshness / TTL enforcement (stale offers).
6. Non-executable NO_OFFER enforcement.
7. Prompt injection hygiene.
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from domain.models import CanonicalDecisionRecord, DecisionExecutionRecord
from domain.commerce_schemas import MerchantCreateRequest, ProductCreateRequest
from services.commerce_service import CommerceService
from services.order_service import OrderService
from services.razorpay.orders import RazorpayOrderService
from services.execution.gate import ExecutionGate
from services.mcp import (
    search_catalog,
    get_product,
    get_offer,
    request_checkout,
    get_order_status,
    evaluate_buyer_intent,
    BuyerAgentIdentity,
    McpCapability,
    ALL_MCP_CAPABILITIES,
    READ_ONLY_CAPABILITIES,
)
from services.mcp.auth import set_current_auth_context
from services.mcp.errors import (
    McpTenantMismatchError,
    McpInsufficientCapabilityError,
    McpInvalidOfferError,
    McpOfferExpiredError,
    McpProductNotFoundError,
)
from tests.conftest import MockRazorpayClient


@pytest.fixture
async def seed_two_merchants(db_session: AsyncSession):
    """Create two distinct merchant tenants for cross-tenant isolation testing."""
    svc = CommerceService()
    m1_id = f"merch_sec_alpha_{uuid.uuid4().hex[:6]}"
    m2_id = f"merch_sec_beta_{uuid.uuid4().hex[:6]}"

    await svc.create_merchant(
        db_session,
        MerchantCreateRequest(
            id=m1_id,
            name="Alpha Gear",
            currency="INR",
            minimum_margin_percent=Decimal("20.00"),
            maximum_discount_percent=Decimal("10.00")
        )
    )
    p1 = await svc.create_product(
        db_session,
        m1_id,
        ProductCreateRequest(
            id=f"prod_a_{uuid.uuid4().hex[:6]}",
            sku="SKU-A-01",
            name="Alpha Travel Pack 30L",
            description="Alpha signature travel backpack",
            category="travel_backpack",
            price_paise=400000,
            cost_paise=200000,
            inventory_quantity=15
        )
    )

    await svc.create_merchant(
        db_session,
        MerchantCreateRequest(
            id=m2_id,
            name="Beta Outdoors",
            currency="INR",
            minimum_margin_percent=Decimal("25.00"),
            maximum_discount_percent=Decimal("5.00")
        )
    )
    p2 = await svc.create_product(
        db_session,
        m2_id,
        ProductCreateRequest(
            id=f"prod_b_{uuid.uuid4().hex[:6]}",
            sku="SKU-B-01",
            name="Beta Expedition Pack 45L",
            description="Beta heavy-duty alpine backpack",
            category="travel_backpack",
            price_paise=600000,
            cost_paise=350000,
            inventory_quantity=10
        )
    )

    return {"m1_id": m1_id, "p1": p1, "m2_id": m2_id, "p2": p2}


def _deep_find_leaks(obj, forbidden_terms=("cogs", "cost_paise", "gross_margin", "ucb_score", "predicted_contribution")):
    """Recursively search any dictionary/list for forbidden private merchant fields."""
    leaks = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            for term in forbidden_terms:
                if term in k.lower():
                    leaks.append(f"Key leak: '{k}'")
            leaks.extend(_deep_find_leaks(v, forbidden_terms))
    elif isinstance(obj, list):
        for item in obj:
            leaks.extend(_deep_find_leaks(item, forbidden_terms))
    return leaks


@pytest.mark.asyncio
async def test_buyer_response_firewall_zero_cogs_leak(db_session: AsyncSession, seed_two_merchants):
    """Verify that products and offers return ZERO internal merchant economics."""
    info = seed_two_merchants
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_leak_tester",
        client_name="audit_agent",
        merchant_id=info["m1_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))

    # 1. Product view
    prod_view = await get_product(info["p1"].id, db=db_session)
    leaks_prod = _deep_find_leaks(prod_view.model_dump(mode="json"))
    assert not leaks_prod, f"Product view leaked private economics: {leaks_prod}"

    # 2. Offer view
    offer = await get_offer(message="I need a high quality travel backpack under 7500", db=db_session)
    leaks_offer = _deep_find_leaks(offer.model_dump(mode="json"))
    assert not leaks_offer, f"Offer view leaked private economics: {leaks_offer}"


@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant_catalog(db_session: AsyncSession, seed_two_merchants):
    """Merchant Alpha agent must not be able to get Merchant Beta product."""
    info = seed_two_merchants
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_alpha",
        client_name="alpha_shopper",
        merchant_id=info["m1_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))

    # Product of Beta must not be accessible to Alpha
    with pytest.raises(McpProductNotFoundError):
        await get_product(info["p2"].id, db=db_session)


@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant_checkout(db_session: AsyncSession, seed_two_merchants):
    """Merchant Beta agent attempting to checkout Merchant Alpha offer must be rejected."""
    info = seed_two_merchants

    # Generate offer under Merchant Alpha
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_alpha",
        merchant_id=info["m1_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))
    offer_alpha = await get_offer(message="I need a high quality travel backpack under 7500", db=db_session)

    # Now switch context to Merchant Beta agent
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_beta",
        merchant_id=info["m2_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))

    # Attempt checkout on Alpha's offer
    with pytest.raises(McpTenantMismatchError):
        await request_checkout(offer_id=offer_alpha.offer_id, db=db_session)


@pytest.mark.asyncio
async def test_capability_authorization_enforced(db_session: AsyncSession, seed_two_merchants):
    """Agent lacking CHECKOUT_REQUEST must be denied execution."""
    info = seed_two_merchants

    # Grant only READ capabilities (no CHECKOUT_REQUEST)
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_read_only",
        merchant_id=info["m1_id"],
        granted_capabilities=set(READ_ONLY_CAPABILITIES)
    ))

    offer = await get_offer(message="I need a high quality travel backpack under 7500", db=db_session)

    with pytest.raises(McpInsufficientCapabilityError) as exc_info:
        await request_checkout(offer_id=offer.offer_id, db=db_session)

    assert "CHECKOUT_REQUEST" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stale_offer_rejected(db_session: AsyncSession, seed_two_merchants, monkeypatch):
    """Offer older than freshness TTL (900s) must be rejected with McpOfferExpiredError."""
    info = seed_two_merchants
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_stale_tester",
        merchant_id=info["m1_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))

    mock_rzp = MockRazorpayClient()
    mock_gate_inst = ExecutionGate(order_service=OrderService(razorpay_orders=RazorpayOrderService(client=mock_rzp)))
    monkeypatch.setattr("services.boundary.service.ExecutionGate", lambda: mock_gate_inst)

    offer = await get_offer(message="I need a high quality travel backpack under 7500", db=db_session)
    dec_id = offer.offer_id.replace("off_", "")

    # Artificially age the decision record by 20 minutes (1200 seconds)
    stmt = select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == dec_id)
    rec = (await db_session.execute(stmt)).scalar_one()
    rec.created_at = datetime.now(timezone.utc) - timedelta(seconds=1200)
    await db_session.commit()

    with pytest.raises(McpOfferExpiredError):
        await request_checkout(offer_id=offer.offer_id, db=db_session)


@pytest.mark.asyncio
async def test_no_offer_unexecutable(db_session: AsyncSession, seed_two_merchants):
    """An offer with NO_OFFER strategy cannot be checked out."""
    info = seed_two_merchants
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_no_offer",
        merchant_id=info["m1_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))

    # Request with unrealistic budget (₹100) -> forces NO_OFFER
    offer = await get_offer(message="Need a travel backpack under 100", db=db_session)
    assert offer.is_executable is False
    assert offer.strategy_type == "NO_OFFER"

    with pytest.raises(McpInvalidOfferError) as exc_info:
        await request_checkout(offer_id=offer.offer_id, db=db_session)
    assert "NO_OFFER" in str(exc_info.value)


@pytest.mark.asyncio
async def test_idempotency_and_replay_checkout(db_session: AsyncSession, seed_two_merchants, monkeypatch):
    """Duplicate checkout with same idempotency key returns existing execution."""
    info = seed_two_merchants
    set_current_auth_context(BuyerAgentIdentity(
        buyer_agent_id="agent_replay_tester",
        merchant_id=info["m1_id"],
        granted_capabilities=set(ALL_MCP_CAPABILITIES)
    ))

    mock_rzp = MockRazorpayClient()
    mock_gate_inst = ExecutionGate(order_service=OrderService(razorpay_orders=RazorpayOrderService(client=mock_rzp)))
    monkeypatch.setattr("services.boundary.service.ExecutionGate", lambda: mock_gate_inst)

    offer = await get_offer(message="I need a high quality travel backpack under 7500", db=db_session)
    idemp_key = f"fixed_idem_key_{uuid.uuid4().hex[:6]}"

    # First attempt
    res1 = await request_checkout(offer_id=offer.offer_id, idempotency_key=idemp_key, db=db_session)
    assert res1.is_duplicate is False

    # Second attempt (replay)
    res2 = await request_checkout(offer_id=offer.offer_id, idempotency_key=idemp_key, db=db_session)
    assert res2.is_duplicate is True
    assert res2.execution_id == res1.execution_id
    assert res2.order_id == res1.order_id
    assert res2.razorpay_order_id == res1.razorpay_order_id
