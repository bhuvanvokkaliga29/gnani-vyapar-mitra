"""End-to-end integration tests for Model Context Protocol (MCP) HTTP interface.

Contract: mcp-commerce/v1
Tests full JSON-RPC 2.0 flow, REST convenience endpoints, and SSE stream.
"""

import pytest
import json
import uuid
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from domain.commerce_schemas import MerchantCreateRequest, ProductCreateRequest
from services.commerce_service import CommerceService
from services.order_service import OrderService
from services.razorpay.orders import RazorpayOrderService
from services.execution.gate import ExecutionGate
from tests.conftest import MockRazorpayClient


@pytest.fixture
async def seed_e2e_merchant(db_session: AsyncSession):
    """Seed Atlas Travel Gear merchant for end-to-end testing."""
    svc = CommerceService()
    merch_id = "merch_atlas_travel"

    await svc.create_merchant(
        db_session,
        MerchantCreateRequest(
            id=merch_id,
            name="Atlas Travel Gear",
            currency="INR",
            business_objective="BALANCE_REVENUE_AND_MARGIN",
            minimum_margin_percent=Decimal("25.00"),
            maximum_discount_percent=Decimal("8.00"),
            target_aov_paise=400000
        )
    )

    await svc.create_product(
        db_session,
        merch_id,
        ProductCreateRequest(
            id="prod_atlas_backpack",
            sku="SKU-ATLAS-01",
            name="Atlas All-Weather Travel Backpack (35L)",
            description="Premium ergonomic carry-on travel backpack",
            category="travel_backpack",
            price_paise=299900,
            cost_paise=150000,
            inventory_quantity=25,
            reserved_quantity=0,
            attributes={"waterproof": True, "volume_l": 35}
        )
    )

    return {"merchant_id": merch_id}


@pytest.mark.asyncio
async def test_mcp_discovery_rest(client: AsyncClient, seed_e2e_merchant):
    """Verify tool discovery via GET /api/v1/mcp/tools and resources via /api/v1/mcp/resources."""
    resp = await client.get("/api/v1/mcp/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    tool_names = [t["name"] for t in data["tools"]]
    assert "search_catalog" in tool_names
    assert "request_checkout" in tool_names

    resp_res = await client.get("/api/v1/mcp/resources")
    assert resp_res.status_code == 200
    res_data = resp_res.json()
    assert "resources" in res_data
    uris = [r["uri"] for r in res_data["resources"]]
    assert "merchant://capabilities" in uris


@pytest.mark.asyncio
async def test_mcp_jsonrpc_full_buyer_journey(client: AsyncClient, seed_e2e_merchant, monkeypatch):
    """Verify canonical buyer journey through JSON-RPC 2.0 dispatcher POST /api/v1/mcp."""
    mock_rzp = MockRazorpayClient()
    mock_gate_inst = ExecutionGate(order_service=OrderService(razorpay_orders=RazorpayOrderService(client=mock_rzp)))
    monkeypatch.setattr("services.boundary.service.ExecutionGate", lambda: mock_gate_inst)

    headers = {
        "X-Buyer-Agent-Id": "agent_e2e_shopper",
        "Authorization": "Bearer merch_atlas_travel"
    }

    # 1. tools/list
    resp = await client.post("/api/v1/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/list"
    })
    assert resp.status_code == 200
    tools_res = resp.json()["result"]["tools"]
    assert len(tools_res) >= 6

    # 2. tools/call -> search_catalog
    resp = await client.post("/api/v1/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "search_catalog",
            "arguments": {"query": "backpack"}
        }
    })
    assert resp.status_code == 200
    catalog_items = resp.json()["result"]["structured_content"]
    assert len(catalog_items) >= 1
    assert catalog_items[0]["name"] == "Atlas All-Weather Travel Backpack (35L)"

    # 3. tools/call -> evaluate_buyer_intent
    resp = await client.post("/api/v1/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "id": "3",
        "method": "tools/call",
        "params": {
            "name": "evaluate_buyer_intent",
            "arguments": {"message": "I need a high quality travel backpack under 7500"}
        }
    })
    assert resp.status_code == 200
    intent = resp.json()["result"]["structured_content"]
    assert intent["category"] == "travel_backpack"
    assert intent["budget_paise"] == 750000

    # 4. tools/call -> get_offer
    resp = await client.post("/api/v1/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "id": "4",
        "method": "tools/call",
        "params": {
            "name": "get_offer",
            "arguments": {"message": "I need a high quality travel backpack under 7500"}
        }
    })
    assert resp.status_code == 200
    offer = resp.json()["result"]["structured_content"]
    assert offer["offer_id"].startswith("off_dec_")
    assert offer["is_executable"] is True
    assert 0 < offer["offered_price_paise"] <= 299900
    offer_id = offer["offer_id"]

    # 5. tools/call -> request_checkout
    resp = await client.post("/api/v1/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "id": "5",
        "method": "tools/call",
        "params": {
            "name": "request_checkout",
            "arguments": {"offer_id": offer_id, "idempotency_key": f"e2e_idem_{uuid.uuid4().hex[:6]}"}
        }
    })
    assert resp.status_code == 200
    checkout = resp.json()["result"]["structured_content"]
    assert checkout["status"] == "EXECUTION_COMPLETED"
    assert checkout["order_id"] is not None
    assert checkout["razorpay_order_id"] is not None
    order_id = checkout["order_id"]

    # 6. tools/call -> get_order_status
    resp = await client.post("/api/v1/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "id": "6",
        "method": "tools/call",
        "params": {
            "name": "get_order_status",
            "arguments": {"order_id": order_id}
        }
    })
    assert resp.status_code == 200
    order_status = resp.json()["result"]["structured_content"]
    assert order_status["order_id"] == order_id
    assert order_status["status"] == "ORDER_CREATED"


@pytest.mark.asyncio
async def test_mcp_sse_handshake(client: AsyncClient):
    """Verify Server-Sent Events stream initialization at /api/v1/mcp/sse."""
    resp = await client.get("/api/v1/mcp/sse")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
