"""Unit and Integration Tests for Twilio WhatsApp Sandbox Integration.

Verifies:
1. Twilio request signature validation & spoof defense.
2. Inbound form data processing & phone normalization.
3. Multilingual intent routing via synchronous TwiML responses.
4. Deterministic policy margin guardrail & compliant alternative floor via TwiML.
5. Confirmation token lifecycle (YES/CONFIRM) via Twilio.
6. Twilio MessageSid deduplication ledger.
7. Webhook endpoints /webhook/twilio & /api/v1/whatsapp/twilio.
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator

from domain.models import Merchant, Product
from services.whatsapp.twilio_adapter import TwilioWhatsAppAdapter


@pytest.fixture
async def seeded_merchant(db_session: AsyncSession):
    """Seed test merchant and product for Twilio WhatsApp tests."""
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

    await db_session.commit()
    await db_session.refresh(merchant)
    await db_session.refresh(backpack)
    return merchant, backpack


def test_twilio_signature_validation():
    """Tests Twilio RequestValidator signature validation logic."""
    token = "test_twilio_auth_token_secret"
    adapter = TwilioWhatsAppAdapter()
    adapter.auth_token = token

    url = "https://example.com/webhook/twilio"
    form = {"From": "whatsapp:+919113960498", "Body": "Hello"}

    # Compute valid signature
    validator = RequestValidator(token)
    valid_sig = validator.compute_signature(url, form)

    assert adapter.validate_signature(url, form, valid_sig) is True
    assert adapter.validate_signature(url, form, "invalid_sig") is False
    assert adapter.validate_signature(url, form, None) is False


@pytest.mark.asyncio
async def test_twilio_kannada_price_change_guardrail_rejection(db_session: AsyncSession, seeded_merchant):
    """
    Simulates merchant sending Kannada price cut command to Twilio WhatsApp Sandbox:
    'Ee black bag price 1800 inda 1600 maadu'.
    Verifies that synchronous TwiML response rejects negative margin and suggests ₹2,400.
    """
    adapter = TwilioWhatsAppAdapter()
    adapter.auth_token = ""  # Dev test mode

    form = {
        "From": "whatsapp:+919113960498",
        "To": "whatsapp:+14155238886",
        "Body": "Ee black bag price 1800 inda 1600 maadu",
        "MessageSid": "SM_test_kannada_001"
    }

    twiml, reply_text, meta = await adapter.process_inbound_webhook(
        db=db_session,
        form_data=form
    )

    assert "<Response>" in twiml
    assert "<Message>" in twiml
    assert "2400" in reply_text
    assert "1600" in reply_text
    assert meta["status"] == "success"
    assert meta["sender_phone"] == "919113960498"


@pytest.mark.asyncio
async def test_twilio_confirmation_via_twiml(db_session: AsyncSession, seeded_merchant):
    """Tests confirming the safe floor via Twilio TwiML."""
    merchant, backpack = seeded_merchant
    adapter = TwilioWhatsAppAdapter()
    adapter.auth_token = ""

    # Step 1: Request violating price -> creates pending confirmation for ₹2,400
    form1 = {
        "From": "whatsapp:+919113960498",
        "Body": "Ee black bag price 1800 inda 1600 maadu",
        "MessageSid": "SM_test_step1"
    }
    await adapter.process_inbound_webhook(db_session, form1)

    # Step 2: Confirm via 'YES'
    form2 = {
        "From": "whatsapp:+919113960498",
        "Body": "YES",
        "MessageSid": "SM_test_step2"
    }
    twiml, reply_text, meta = await adapter.process_inbound_webhook(db_session, form2)

    assert "<Response>" in twiml
    assert "2400" in reply_text
    assert "ಯಶಸ್ವಿಯಾಗಿದೆ" in reply_text or "Successfully" in reply_text

    # Verify catalog updated in DB
    await db_session.refresh(backpack)
    assert backpack.price_paise == 240000


@pytest.mark.asyncio
async def test_twilio_messagesid_deduplication(db_session: AsyncSession, seeded_merchant):
    """Tests duplicate MessageSid is acknowledged with empty TwiML <Response/> without repeated execution."""
    adapter = TwilioWhatsAppAdapter()
    adapter.auth_token = ""

    form = {
        "From": "whatsapp:+919113960498",
        "Body": "Stock eshtu ide nodu",
        "MessageSid": "SM_test_duplicate_sid_001"
    }

    # 1. First execution
    twiml1, reply1, meta1 = await adapter.process_inbound_webhook(db_session, form)
    assert meta1["status"] == "success"

    # 2. Duplicate submission with identical MessageSid
    twiml2, reply2, meta2 = await adapter.process_inbound_webhook(db_session, form)
    assert meta2["status"] == "duplicate"
    assert twiml2 == "<Response/>"


@pytest.mark.asyncio
async def test_twilio_webhook_endpoint_http(client: AsyncClient, seeded_merchant):
    """Tests HTTP POST /webhook/twilio endpoint with form data."""
    data = {
        "From": "whatsapp:+919113960498",
        "To": "whatsapp:+14155238886",
        "Body": "Change backpack price to 2500",
        "MessageSid": "SM_http_endpoint_test_001"
    }

    resp = await client.post("/webhook/twilio", data=data)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "<Response>" in resp.text
    assert "2500" in resp.text
