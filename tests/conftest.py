"""Pytest Fixtures for Unit and Integration Tests."""

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from apps.api.core.database import get_db
from domain.models import Base
from services.razorpay.client import RazorpayClient
from services.razorpay.orders import RazorpayOrderService
from services.razorpay.models import RazorpayOrderResponse, RazorpayPaymentCollection, RazorpayPaymentItem

# In-memory test SQLite engine
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    future=True
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a clean event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session with freshly created schema for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP async test client with database dependency override."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client

    app.dependency_overrides.clear()


class MockRazorpayClient(RazorpayClient):
    """Mock client returning deterministic responses for integration testing."""

    def __init__(self):
        super().__init__(key_id="rzp_test_mock_id", key_secret="mock_secret")
        self.orders_db = {}
        self.payments_db = {}

    async def request(self, method: str, path: str, json_data=None, params=None):
        if method == "POST" and path == "orders":
            order_id = f"order_mock_{len(self.orders_db) + 1}"
            resp = {
                "id": order_id,
                "entity": "order",
                "amount": json_data.get("amount", 10000),
                "amount_paid": 0,
                "amount_due": json_data.get("amount", 10000),
                "currency": json_data.get("currency", "INR"),
                "receipt": json_data.get("receipt", ""),
                "status": "created",
                "created_at": 1725364800,
                "notes": json_data.get("notes", {})
            }
            self.orders_db[order_id] = resp
            return resp

        elif method == "GET" and path.startswith("orders/"):
            order_id = path.split("/")[1]
            if "payments" in path:
                # Return payments for order
                pmts = [p for p in self.payments_db.values() if p.get("order_id") == order_id]
                return {"entity": "collection", "count": len(pmts), "items": pmts}
            elif order_id in self.orders_db:
                return self.orders_db[order_id]
            raise Exception("Order not found")

        elif method == "GET" and path == "orders":
            items = list(self.orders_db.values())
            return {"entity": "collection", "count": len(items), "items": items}

        return {}
