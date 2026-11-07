"""Unit and integration tests for Gnani AI Agent Builder integration."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from apps.api.core.config import settings
from services.voice.gnani_agent_client import GnaniAgentBuilderClient


@pytest.mark.asyncio
async def test_gnani_agent_client_configuration():
    """Verify GnaniAgentBuilderClient loads configuration properly."""
    client = GnaniAgentBuilderClient()
    assert client.agent_id == "7bd15e5ff5a7411db02665f468d3353a"
    assert "inya.ai" in client.base_url
    headers = client._get_headers()
    assert "x-api-key" in headers
    assert "application/json" in headers["Content-Type"]


@pytest.mark.asyncio
async def test_gnani_agent_status_endpoint():
    """Verify GET /api/v1/gnani-agent/status returns accurate diagnostics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/gnani-agent/status")
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is False or data["configured"] is True
        assert data["bot_id"] == "7bd15e5ff5a7411db02665f468d3353a"
        assert "probe_status_code" in data
        assert "diagnostics" in data


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_daily_sales():
    """Verify Gnani Custom Action webhook executes get_daily_sales."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/action", json={
            "action": "get_daily_sales",
            "merchant_id": "merch_atlas_travel"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "revenue" in data["data"]
        assert "total_orders" in data["data"]


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_top_products():
    """Verify Gnani Custom Action webhook executes get_top_products."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/action", json={
            "action": "get_top_products",
            "merchant_id": "merch_atlas_travel",
            "limit": 2
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert len(data["data"]["top_products"]) <= 2


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_product_stock():
    """Verify Gnani Custom Action webhook executes get_product_stock."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/action", json={
            "action": "get_product_stock",
            "merchant_id": "merch_atlas_travel",
            "sku": "VAST-SH-03"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["data"]["sku"] == "VAST-SH-03"


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_profit_summary():
    """Verify Gnani Custom Action webhook executes get_profit_summary."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/action", json={
            "action": "get_profit_summary",
            "merchant_id": "merch_atlas_travel"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "gross_profit_formatted" in data["data"]
        assert "gross_margin_percent" in data["data"]


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_missing_merchant():
    """Verify Gnani Custom Action webhook rejects unknown merchant IDs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/action", json={
            "action": "get_daily_sales",
            "merchant_id": "non_existent_merchant_xyz"
        })
        assert res.status_code == 404
        assert "not found" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_missing_sku():
    """Verify Gnani Custom Action webhook returns structured failure for missing SKU."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/action", json={
            "action": "get_product_stock",
            "merchant_id": "merch_atlas_travel",
            "sku": "NON_EXISTENT_SKU_999"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "failure"
        assert "not found" in data["message"].lower()


@pytest.mark.asyncio
async def test_gnani_post_call_webhook_session_continuity():
    """Verify post-call webhook creates session and persists transcript turns."""
    import uuid
    unique_conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/gnani-agent/webhook", json={
            "conversation_id": unique_conv_id,
            "merchant_id": "merch_atlas_travel",
            "transcript": [
                {"role": "user", "content": "Hello, how much stock is remaining in linen shirts?"},
                {"role": "assistant", "content": "You have 145 units in stock."}
            ]
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["turns_saved"] == 2
        assert data["session_id"].startswith("vcs_")


@pytest.mark.asyncio
async def test_gnani_post_call_webhook_duplicate_protection():
    """Verify post-call webhook ignores duplicate conversation IDs."""
    import uuid
    dup_conv_id = f"dup_{uuid.uuid4().hex[:12]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First delivery
        res1 = await ac.post("/api/v1/gnani-agent/webhook", json={
            "conversation_id": dup_conv_id,
            "merchant_id": "merch_atlas_travel",
            "transcript": [
                {"role": "user", "content": "First turn"}
            ]
        })
        assert res1.status_code == 200

        # Duplicate delivery
        res2 = await ac.post("/api/v1/gnani-agent/webhook", json={
            "conversation_id": dup_conv_id,
            "merchant_id": "merch_atlas_travel",
            "transcript": [
                {"role": "user", "content": "First turn duplicate"}
            ]
        })
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "duplicate_ignored"


@pytest.mark.asyncio
async def test_gnani_custom_action_webhook_unauthorized_with_invalid_secret():
    """Verify webhook rejects requests with invalid secret header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/gnani-agent/action",
            json={
                "action": "get_daily_sales",
                "merchant_id": "merch_atlas_travel"
            },
            headers={"X-Gnani-Secret": "invalid_secret_attack"}
        )
        assert res.status_code == 401
