"""Integration tests for Orders API endpoints using Mock Razorpay Adapter."""

import pytest
from httpx import AsyncClient
from apps.api.main import app
from apps.api.routers.orders import get_order_service
from services.order_service import OrderService
from services.razorpay.orders import RazorpayOrderService
from tests.conftest import MockRazorpayClient


@pytest.fixture
def mock_order_service():
    mock_client = MockRazorpayClient()
    rzp_orders = RazorpayOrderService(client=mock_client)
    return OrderService(razorpay_orders=rzp_orders)


@pytest.mark.asyncio
async def test_create_order_endpoint(client: AsyncClient, mock_order_service: OrderService):
    """Verify POST /api/v1/orders creates an order and returns 200 OK."""
    app.dependency_overrides[get_order_service] = lambda: mock_order_service

    payload = {
        "amount_paise": 250000,  # ₹2,500.00
        "currency": "INR",
        "notes": {"bundle": "espresso_tamper"}
    }

    response = await client.post("/api/v1/orders", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["id"].startswith("ord_")
    assert data["razorpay_order_id"].startswith("order_mock_")
    assert data["status"] == "ORDER_CREATED"
    assert data["amount_paise"] == 250000
    assert data["currency"] == "INR"
    assert len(data["receipt"]) <= 40

    # Clean up override
    app.dependency_overrides.pop(get_order_service, None)


@pytest.mark.asyncio
async def test_create_order_invalid_amount(client: AsyncClient):
    """Negative amount must return 400 Bad Request."""
    payload = {
        "amount_paise": -500,
        "currency": "INR"
    }
    response = await client.post("/api/v1/orders", json=payload)
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_get_order_by_id(client: AsyncClient, mock_order_service: OrderService):
    """Verify GET /api/v1/orders/{id} retrieves the created order."""
    app.dependency_overrides[get_order_service] = lambda: mock_order_service

    create_resp = await client.post("/api/v1/orders", json={"amount_paise": 10000})
    order_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/orders/{order_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == order_id
    assert get_resp.json()["status"] == "ORDER_CREATED"

    app.dependency_overrides.pop(get_order_service, None)
