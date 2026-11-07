"""Integration tests for inbound webhook processing, HMAC verification, and deduplication."""

import json
import hmac
import hashlib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import Order, Payment, ProcessedWebhookEvent, AuditEvent
from apps.api.core.config import settings


@pytest.mark.asyncio
async def test_successful_webhook_payment_flow(client: AsyncClient, db_session: AsyncSession):
    """Full lifecycle: create order -> receive signed order.paid webhook -> verify state transition to PAID."""
    # 1. Create Order in local DB
    order = Order(
        id="ord_test_flow_1",
        decision_id="dec_test_flow_1",
        razorpay_order_id="order_flow_123",
        amount_paise=50000,
        currency="INR",
        receipt="dec_test_flow_1",
        status="ORDER_CREATED"
    )
    db_session.add(order)
    await db_session.commit()

    # 2. Build signed Razorpay webhook payload
    webhook_payload = {
        "entity": "event",
        "account_id": "acc_test_123",
        "event": "order.paid",
        "contains": ["order", "payment"],
        "payload": {
            "order": {
                "entity": {
                    "id": "order_flow_123",
                    "amount": 50000,
                    "status": "paid"
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_flow_999",
                    "order_id": "order_flow_123",
                    "amount": 50000,
                    "status": "captured",
                    "method": "upi"
                }
            }
        },
        "created_at": 1725364900
    }

    raw_body = json.dumps(webhook_payload).encode("utf-8")
    signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
        "X-Razorpay-Event-Id": "evt_flow_unique_1"
    }

    # 3. Post webhook to application endpoint
    response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    # 4. Verify DB State: Order status is PAID
    await db_session.refresh(order)
    assert order.status == "PAID"

    # Verify Payment row created
    pmt_stmt = select(Payment).where(Payment.id == "pay_flow_999")
    pmt_res = await db_session.execute(pmt_stmt)
    payment = pmt_res.scalar_one_or_none()
    assert payment is not None
    assert payment.status == "captured"
    assert payment.amount_paise == 50000

    # Verify ProcessedWebhookEvent recorded
    evt_stmt = select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == "evt_flow_unique_1")
    evt_res = await db_session.execute(evt_stmt)
    evt = evt_res.scalar_one_or_none()
    assert evt is not None

    # 5. Duplicate Webhook: Re-transmit identical webhook
    dup_response = await client.post("/webhooks/razorpay", content=raw_body, headers=headers)
    assert dup_response.status_code == 200
    assert dup_response.json()["status"] == "already_processed"
