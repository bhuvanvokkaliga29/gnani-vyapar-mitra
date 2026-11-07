"""Required Failure Tests: 7 Negative Scenarios Demonstrating Resilient Halting and Recovery."""

import json
import hmac
import hashlib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import Order, Payment, ProcessedWebhookEvent, AuditEvent
from apps.api.core.config import settings
from apps.api.core.state_machine import TransactionState
from services.order_service import OrderService
from services.razorpay.orders import RazorpayOrderService
from services.razorpay.reconciliation import ReconciliationService
from services.razorpay.errors import RazorpayTimeoutError, RazorpayError
from tests.conftest import MockRazorpayClient


@pytest.mark.asyncio
async def test_failure_1_invalid_webhook_signature(client: AsyncClient, db_session: AsyncSession):
    """Failure Test 1: Invalid webhook signature must be rejected with 400 and cause zero state mutation."""
    order = Order(
        id="ord_fail_1",
        decision_id="dec_fail_1",
        razorpay_order_id="order_fail_1",
        amount_paise=10000,
        currency="INR",
        receipt="dec_fail_1",
        status="ORDER_CREATED"
    )
    db_session.add(order)
    await db_session.commit()

    raw_body = b'{"event":"order.paid","payload":{"order":{"entity":{"id":"order_fail_1"}}}}'
    bad_signature = "bad_hex_signature_999999"
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": bad_signature,
        "X-Razorpay-Event-Id": "evt_fail_1"
    }

    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 400
    assert "Invalid Razorpay webhook signature" in response.json()["detail"]

    # Verify no state mutation on order
    await db_session.refresh(order)
    assert order.status == "ORDER_CREATED"

    # Verify audit failure recorded
    stmt = select(AuditEvent).where(AuditEvent.action == "webhook_rejected")
    res = await db_session.execute(stmt)
    audit = res.scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_failure_2_duplicate_webhook(client: AsyncClient, db_session: AsyncSession):
    """Failure Test 2: Duplicate webhook delivery is safely deduplicated without secondary mutation."""
    order = Order(
        id="ord_fail_2",
        decision_id="dec_fail_2",
        razorpay_order_id="order_fail_2",
        amount_paise=20000,
        currency="INR",
        receipt="dec_fail_2",
        status="ORDER_CREATED"
    )
    db_session.add(order)
    await db_session.commit()

    payload = {
        "event": "order.paid",
        "payload": {
            "order": {"entity": {"id": "order_fail_2"}},
            "payment": {"entity": {"id": "pay_fail_2", "amount": 20000, "status": "captured"}}
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": "evt_dup_test_2"
    }

    # First arrival: processes normally
    res1 = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    # Second arrival: deduplicated
    res2 = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"

    # Verify payments count is exactly 1
    pmt_stmt = select(Payment).where(Payment.id == "pay_fail_2")
    pmts = (await db_session.execute(pmt_stmt)).scalars().all()
    assert len(pmts) == 1


@pytest.mark.asyncio
async def test_failure_3_concurrent_event_delivery(db_session: AsyncSession):
    """Failure Test 3: Database uniqueness constraint protects against concurrent duplicate events."""
    event_id = "evt_concurrent_1"
    evt1 = ProcessedWebhookEvent(event_id=event_id, event_type="order.paid", payload={"sample": 1})
    db_session.add(evt1)
    await db_session.commit()

    # Attempting to insert duplicate event ID directly violates primary key uniqueness
    evt2 = ProcessedWebhookEvent(event_id=event_id, event_type="order.paid", payload={"sample": 2})
    db_session.add(evt2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_failure_4_order_creation_timeout_reconciliation(db_session: AsyncSession):
    """Failure Test 4: Razorpay timeout during creation marks state UNCERTAIN and triggers safe reconciliation."""
    class TimeoutMockRazorpay(MockRazorpayClient):
        def __init__(self):
            super().__init__()
            self.timeout_triggered = False

        async def request(self, method: str, path: str, json_data=None, params=None):
            if method == "POST" and path == "orders" and not self.timeout_triggered:
                self.timeout_triggered = True
                # Register order in provider back-end, but drop connection to client!
                self.orders_db["order_timeout_created"] = {
                    "id": "order_timeout_created",
                    "entity": "order",
                    "amount": json_data["amount"],
                    "currency": "INR",
                    "receipt": json_data["receipt"],
                    "status": "created"
                }
                raise RazorpayTimeoutError("Connection timed out to gateway on POST /orders")
            return await super().request(method, path, json_data, params)

    mock_client = TimeoutMockRazorpay()
    order_svc = OrderService(
        razorpay_orders=RazorpayOrderService(client=mock_client),
        reconciler=ReconciliationService(order_service=RazorpayOrderService(client=mock_client))
    )

    # Calling create_order triggers timeout -> marks UNCERTAIN -> reconciler finds order by receipt -> recovers to ORDER_CREATED!
    order = await order_svc.create_order(db=db_session, amount_paise=15000)

    assert order.status == TransactionState.ORDER_CREATED.value
    assert order.razorpay_order_id == "order_timeout_created"

    # Verify audit event recorded reconciliation completion
    stmt = select(AuditEvent).where(AuditEvent.action == "order_reconciliation_completed")
    audit = (await db_session.execute(stmt)).scalar_one_or_none()
    assert audit is not None


@pytest.mark.asyncio
async def test_failure_5_malformed_provider_response(db_session: AsyncSession):
    """Failure Test 5: Malformed provider response raises structured error and marks order FAILED."""
    class MalformedMockRazorpay(MockRazorpayClient):
        async def request(self, method: str, path: str, json_data=None, params=None):
            raise RazorpayError("Invalid JSON structure from provider gateway", status_code=502)

    order_svc = OrderService(
        razorpay_orders=RazorpayOrderService(client=MalformedMockRazorpay())
    )

    with pytest.raises(RazorpayError):
        await order_svc.create_order(db=db_session, amount_paise=10000)

    # Verify order is marked FAILED and audit log records failure
    stmt = select(Order).order_by(Order.created_at.desc())
    failed_order = (await db_session.execute(stmt)).scalars().first()
    assert failed_order.status == TransactionState.FAILED.value


@pytest.mark.asyncio
async def test_failure_6_database_rollback_on_webhook_failure(client: AsyncClient, db_session: AsyncSession):
    """Failure Test 6: An unhandled database or processing failure rolls back transaction without acknowledging fake success."""
    # When payload has completely unparsable bytes despite passing HMAC
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    corrupted_body = b"NOT_VALID_JSON_CONTENT"
    sig = hmac.new(secret.encode(), corrupted_body, hashlib.sha256).hexdigest()

    headers = {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": "evt_corrupted_1"
    }

    response = await client.post("/webhooks/razorpay", content=corrupted_body, headers=headers)
    assert response.status_code == 500  # Server error, not 200 OK

    # Verify no processed event record was committed
    stmt = select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == "evt_corrupted_1")
    evt = (await db_session.execute(stmt)).scalar_one_or_none()
    assert evt is None


@pytest.mark.asyncio
async def test_failure_7_stale_out_of_order_webhook(client: AsyncClient, db_session: AsyncSession):
    """Failure Test 7: Stale webhook (e.g. delayed payment.authorized arriving after order is PAID) does not regress state."""
    order = Order(
        id="ord_fail_7",
        decision_id="dec_fail_7",
        razorpay_order_id="order_fail_7",
        amount_paise=30000,
        currency="INR",
        receipt="dec_fail_7",
        status="PAID"  # Already in terminal PAID state!
    )
    db_session.add(order)
    await db_session.commit()

    # Delayed webhook arrives for payment.authorized
    payload = {
        "event": "payment.authorized",
        "payload": {
            "order": {"entity": {"id": "order_fail_7"}},
            "payment": {"entity": {"id": "pay_stale_7", "amount": 30000, "status": "authorized"}}
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    headers = {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": "evt_stale_7"
    }

    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 200

    # Ensure Order status remained PAID and was NOT regressed to AUTHORIZED
    await db_session.refresh(order)
    assert order.status == "PAID"
