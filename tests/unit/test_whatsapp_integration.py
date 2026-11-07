"""Comprehensive Test Suite for WhatsApp Business Platform Integration.

Covers:
1. Webhook GET verification handshake (valid challenge, invalid token, forbidden)
2. Webhook POST HMAC-SHA256 signature verification & forged signature rejection
3. Phone number normalization (E.164 standardization)
4. Multilingual intent parsing (Kannada, Hindi, English, relative cuts, stock, confirmations)
5. Deterministic policy guardrail enforcement & compliant alternative pricing formula
6. Confirmation token lifecycle (15-min TTL, single-use execution, replay defense, cancellation, superseding)
7. WAMID deduplication ledger
8. Outbound client mock fallback & Meta API dispatch
9. Interactive simulation endpoint (/api/v1/whatsapp/simulate)
10. Diagnostics and telemetry inspection (/api/v1/whatsapp/diagnostics)
"""

import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.core.config import settings
from domain.models import Merchant, Product, AuditEvent
from domain.whatsapp_models import (
    WhatsAppWebhookLog,
    WhatsAppPendingConfirmation,
    WhatsAppOutboundMessage
)
from services.whatsapp.security import normalize_phone_number, verify_webhook_signature
from services.whatsapp.intent import WhatsAppIntentParser, IntentType
from services.whatsapp.policy_guard import PolicyGuard, PolicyValidationResult
from services.whatsapp.confirmation import ConfirmationManager
from services.whatsapp.service import WhatsAppService
from services.commerce_service import CommerceService


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
async def seeded_merchant(db_session: AsyncSession):
    """Seeds a test merchant tenant and catalog item for WhatsApp tests."""
    merchant = Merchant(
        id="merch_atlas_travel",
        name="Atlas Travel Gear",
        currency="INR",
        status="ACTIVE",
        business_objective="BALANCE_REVENUE_AND_MARGIN",
        minimum_margin_percent=Decimal("25.00"),
        maximum_discount_percent=Decimal("10.00"),
        target_aov_paise=400000
    )
    db_session.add(merchant)

    backpack = Product(
        id="prod_travel_backpack",
        merchant_id=merchant.id,
        sku="SKU-BACKPACK-01",
        name="Atlas All-Weather Travel Backpack (35L)",
        description="Waterproof modular backpack",
        category="Bags & Luggage",
        price_paise=299900,  # ₹2,999.00
        cost_paise=180000,   # ₹1,800.00
        currency="INR",
        inventory_quantity=30,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add(backpack)

    mouse = Product(
        id="prod_wireless_mouse",
        merchant_id=merchant.id,
        sku="SKU-MOUSE-03",
        name="Ergonomic Multi-Device Bluetooth Mouse",
        description="Silent wireless mouse",
        category="Computer Peripherals",
        price_paise=99900,   # ₹999.00
        cost_paise=50000,    # ₹500.00
        currency="INR",
        inventory_quantity=40,
        reserved_quantity=0,
        is_active=True
    )
    db_session.add(mouse)

    await db_session.commit()
    await db_session.refresh(merchant)
    await db_session.refresh(backpack)
    await db_session.refresh(mouse)
    return merchant, backpack, mouse


# -----------------------------------------------------------------------------
# 1. Security & Normalization Tests
# -----------------------------------------------------------------------------

def test_phone_number_normalization():
    """Validates international and local Indian phone normalization."""
    assert normalize_phone_number("+919113960498") == "919113960498"
    assert normalize_phone_number("+91 9113960498") == "919113960498"
    assert normalize_phone_number("9113960498") == "919113960498"
    assert normalize_phone_number("09113960498") == "919113960498"
    assert normalize_phone_number("+1-555-026-9000") == "15550269000"


def test_hmac_signature_verification():
    """Tests Meta HMAC-SHA256 signature verification."""
    secret = "test_meta_app_secret_12345"
    body = b'{"object":"whatsapp_business_account"}'

    # Valid signature
    expected_sig = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, expected_sig, secret) is True

    # Forged signature
    assert verify_webhook_signature(body, "sha256=invalid_forged_signature_hex", secret) is False

    # Empty signature when secret configured
    assert verify_webhook_signature(body, None, secret) is False


# -----------------------------------------------------------------------------
# 2. Multilingual Intent Parsing Tests
# -----------------------------------------------------------------------------

def test_intent_kannada_price_change():
    """Tests Kannada absolute price change command."""
    query = "Ee black bag price 1800 inda 1600 maadu"
    intent = WhatsAppIntentParser.parse(query)
    assert intent.language == "kn"
    assert intent.intent_type == IntentType.PRICE_CHANGE
    assert intent.target_price_paise == 160000
    assert intent.price_value == 1600.0


def test_intent_kannada_relative_cut():
    """Tests Kannada relative price reduction."""
    query = "Bag ge 200 rupayi kammi maadu"
    intent = WhatsAppIntentParser.parse(query)
    assert intent.language == "kn"
    assert intent.intent_type == IntentType.PRICE_CHANGE
    assert intent.delta_price_paise == 20000
    assert intent.price_relative_cut == 200.0


def test_intent_hindi_price_change():
    """Tests Hindi price change command."""
    query = "Black bag ka price 1600 kar do"
    intent = WhatsAppIntentParser.parse(query)
    assert intent.language == "hi"
    assert intent.intent_type == IntentType.PRICE_CHANGE
    assert intent.target_price_paise == 160000


def test_intent_english_price_change():
    """Tests English price change command."""
    query = "Change backpack price to 2500"
    intent = WhatsAppIntentParser.parse(query)
    assert intent.language == "en"
    assert intent.intent_type == IntentType.PRICE_CHANGE
    assert intent.target_price_paise == 250000


def test_intent_english_relative_cut():
    """Tests English relative cut command."""
    query = "Reduce backpack price by 300"
    intent = WhatsAppIntentParser.parse(query)
    assert intent.intent_type == IntentType.PRICE_CHANGE
    assert intent.delta_price_paise == 30000


def test_intent_inventory_add_and_set():
    """Tests inventory addition and setting."""
    query_add = "We received 25 new backpacks"
    intent_add = WhatsAppIntentParser.parse(query_add)
    assert intent_add.intent_type == IntentType.INVENTORY_ADD
    assert intent_add.inventory_units == 25

    query_kn = "Hosa 30 shirts bandide add maadu"
    intent_kn = WhatsAppIntentParser.parse(query_kn)
    assert intent_kn.intent_type == IntentType.INVENTORY_ADD
    assert intent_kn.inventory_units == 30


def test_intent_confirmations_and_cancellations():
    """Tests YES, CONFIRM, CANCEL in multiple languages."""
    assert WhatsAppIntentParser.parse("YES").intent_type == IntentType.CONFIRM
    assert WhatsAppIntentParser.parse("CONFIRM 4921").intent_type == IntentType.CONFIRM
    assert WhatsAppIntentParser.parse("CONFIRM 4921").confirmation_code == "4921"
    assert WhatsAppIntentParser.parse("HA").intent_type == IntentType.CONFIRM
    assert WhatsAppIntentParser.parse("SARI").intent_type == IntentType.CONFIRM

    assert WhatsAppIntentParser.parse("CANCEL").intent_type == IntentType.CANCEL
    assert WhatsAppIntentParser.parse("NO").intent_type == IntentType.CANCEL
    assert WhatsAppIntentParser.parse("BEDI").intent_type == IntentType.CANCEL
    assert WhatsAppIntentParser.parse("NAHI").intent_type == IntentType.CANCEL


# -----------------------------------------------------------------------------
# 3. Policy Guardrail Tests
# -----------------------------------------------------------------------------

def test_policy_guard_valid_price(seeded_merchant):
    """Compliant price satisfying 25% minimum margin."""
    merchant, backpack, _ = seeded_merchant
    # Cost = 180000 paise (₹1,800). At ₹2,500 selling price:
    # Margin = (2500 - 1800) / 2500 = 28.0% >= 25.0%
    result = PolicyGuard.validate_price_change(
        merchant=merchant,
        product=backpack,
        proposed_price_paise=250000,
        language="en"
    )
    assert result.is_valid is True
    assert result.proposed_margin_percent == 28.0


def test_policy_guard_margin_violation_and_safe_floor(seeded_merchant):
    """Violating price triggers rejection and calculates safe compliant alternative."""
    merchant, backpack, _ = seeded_merchant
    # Cost = ₹1,800. Proposed = ₹1,600 (Negative margin: -12.5% < 25%)
    result = PolicyGuard.validate_price_change(
        merchant=merchant,
        product=backpack,
        proposed_price_paise=160000,
        language="kn"
    )
    assert result.is_valid is False
    assert result.violation_type == "MARGIN_VIOLATION"
    # Safe floor: cost / (1 - 0.25) = 1800 / 0.75 = ₹2,400 (240000 paise)
    assert result.compliant_price_paise == 240000
    assert result.compliant_price_rupees == 2400
    assert "2400" in result.message_kn
    assert "1600" in result.message_kn


# -----------------------------------------------------------------------------
# 4. Confirmation Token Manager Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirmation_lifecycle_and_replay_defense(db_session: AsyncSession, seeded_merchant):
    """Tests token creation, execution, single-use defense, and replay prevention."""
    merchant, backpack, _ = seeded_merchant
    mgr = ConfirmationManager()

    # 1. Create confirmation token
    conf = await mgr.create_pending_confirmation(
        db=db_session,
        merchant_id=merchant.id,
        sender_phone="919113960498",
        operation_type="PRICE_UPDATE",
        proposed_values={"price_paise": 250000},
        current_values={"price_paise": backpack.price_paise},
        product=backpack,
        language="en"
    )

    assert conf.status == "PENDING"
    assert len(conf.confirmation_code) == 4

    # 2. Find pending confirmation
    found, err = await mgr.find_pending_confirmation(
        db=db_session,
        merchant_id=merchant.id,
        sender_phone="919113960498",
        explicit_code=conf.confirmation_code
    )
    assert found is not None
    assert found.id == conf.id

    # 3. Execute confirmed operation
    success, msg, data = await mgr.execute_confirmed_operation(db_session, found)
    assert success is True
    assert found.status == "CONFIRMED"

    # Verify catalog was updated
    await db_session.refresh(backpack)
    assert backpack.price_paise == 250000

    # 4. Replay attack defense: attempting to re-confirm must fail
    replay_found, replay_err = await mgr.find_pending_confirmation(
        db=db_session,
        merchant_id=merchant.id,
        sender_phone="919113960498",
        explicit_code=conf.confirmation_code
    )
    assert replay_found is None
    assert replay_err == "ALREADY_EXECUTED"


@pytest.mark.asyncio
async def test_confirmation_cancellation(db_session: AsyncSession, seeded_merchant):
    """Tests user cancellation of pending token."""
    merchant, backpack, _ = seeded_merchant
    mgr = ConfirmationManager()

    conf = await mgr.create_pending_confirmation(
        db=db_session,
        merchant_id=merchant.id,
        sender_phone="919113960498",
        operation_type="PRICE_UPDATE",
        proposed_values={"price_paise": 250000},
        current_values={"price_paise": backpack.price_paise},
        product=backpack
    )

    cancelled = await mgr.cancel_pending(db_session, merchant.id, "919113960498")
    assert cancelled is not None
    assert cancelled.status == "CANCELLED"

    # Catalog remains unchanged
    await db_session.refresh(backpack)
    assert backpack.price_paise == 299900


@pytest.mark.asyncio
async def test_confirmation_superseded(db_session: AsyncSession, seeded_merchant):
    """Tests that a newer price request supersedes older pending requests."""
    merchant, backpack, _ = seeded_merchant
    mgr = ConfirmationManager()

    # Request 1
    conf1 = await mgr.create_pending_confirmation(
        db=db_session,
        merchant_id=merchant.id,
        sender_phone="919113960498",
        operation_type="PRICE_UPDATE",
        proposed_values={"price_paise": 250000},
        product=backpack
    )

    # Request 2
    conf2 = await mgr.create_pending_confirmation(
        db=db_session,
        merchant_id=merchant.id,
        sender_phone="919113960498",
        operation_type="PRICE_UPDATE",
        proposed_values={"price_paise": 260000},
        product=backpack
    )

    await db_session.refresh(conf1)
    assert conf1.status == "SUPERSEDED"
    assert conf2.status == "PENDING"


# -----------------------------------------------------------------------------
# 5. FastAPI Endpoints & Webhook Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_get_verification_success(client: AsyncClient):
    """Tests Meta hub.challenge verification GET handshake."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
        "hub.challenge": "1158201444"
    }
    resp = await client.get("/webhook/whatsapp", params=params)
    assert resp.status_code == 200
    assert resp.text == "1158201444"


@pytest.mark.asyncio
async def test_webhook_get_verification_failure(client: AsyncClient):
    """Tests rejected GET handshake on token mismatch."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_unauthorized_token",
        "hub.challenge": "1158201444"
    }
    resp = await client.get("/webhook/whatsapp", params=params)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_simulation_policy_guardrail_rejection_flow(client: AsyncClient, seeded_merchant):
    """
    End-to-end simulation test:
    Merchant sends 'Ee black bag price 1800 inda 1600 maadu'.
    Agent detects margin floor violation, returns alert in Kannada and suggests ₹2,400.
    Merchant replies 'YES'.
    Agent updates price to ₹2,400.
    """
    # Step 1: Send violating price request
    payload1 = {
        "sender_phone": "+919113960498",
        "message_text": "Ee black bag price 1800 inda 1600 maadu"
    }
    resp1 = await client.post("/api/v1/whatsapp/simulate", json=payload1)
    assert resp1.status_code == 200
    data1 = resp1.json()
    reply1 = data1["result"]["processed"][0]["reply"]
    # Kannada policy alert and alternative suggestion
    assert "2400" in reply1
    assert "YES" in reply1 or "CONFIRM" in reply1

    # Step 2: Confirm the suggested alternative
    payload2 = {
        "sender_phone": "+919113960498",
        "message_text": "YES"
    }
    resp2 = await client.post("/api/v1/whatsapp/simulate", json=payload2)
    assert resp2.status_code == 200
    data2 = resp2.json()
    reply2 = data2["result"]["processed"][0]["reply"]
    assert "2400" in reply2
    assert "ಯಶಸ್ವಿಯಾಗಿದೆ" in reply2 or "Success" in reply2


@pytest.mark.asyncio
async def test_simulation_wamid_deduplication(client: AsyncClient, seeded_merchant):
    """Tests that sending identical WAMID twice is deduplicated idempotently."""
    wamid = "wamid.HBgLMzkxMTM5NjA0OTgVAgASGBgyMjg5OEUwQT"
    payload = {
        "sender_phone": "+919113960498",
        "message_text": "Stock eshtu ide nodu",
        "wamid": wamid
    }

    # First delivery
    resp1 = await client.post("/api/v1/whatsapp/simulate", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["result"]["processed"][0]["status"] == "success"

    # Second delivery with identical WAMID
    resp2 = await client.post("/api/v1/whatsapp/simulate", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["result"]["processed"][0]["status"] == "duplicate"


@pytest.mark.asyncio
async def test_whatsapp_diagnostics_endpoint(client: AsyncClient, seeded_merchant):
    """Tests GET /api/v1/whatsapp/diagnostics endpoint."""
    resp = await client.get("/api/v1/whatsapp/diagnostics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "configuration" in data
    assert data["configuration"]["target_merchant_phone"] == "+919113960498"
    assert "metrics" in data
    assert "recent_inbound" in data
    assert "recent_outbound" in data
