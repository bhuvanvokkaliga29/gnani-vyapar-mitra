"""Unit tests for webhook cryptographic verification and header extraction."""

import hmac
import hashlib
from services.razorpay.webhooks import verify_webhook_signature, extract_event_id


def test_valid_hmac_signature():
    """Verify that a correctly signed raw payload passes verification."""
    secret = "test_webhook_secret_999"
    raw_payload = b'{"event":"order.paid","entity":"event"}'

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        raw_payload,
        hashlib.sha256
    ).hexdigest()

    assert verify_webhook_signature(raw_payload, expected_sig, secret) is True


def test_tampered_payload_fails_verification():
    """Verify that any modification to raw bytes invalidates the signature."""
    secret = "test_webhook_secret_999"
    raw_payload = b'{"event":"order.paid","amount":1000}'
    tampered_payload = b'{"event":"order.paid","amount":1001}'

    sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(tampered_payload, sig, secret) is False


def test_incorrect_secret_fails_verification():
    """Verify that signing with an incorrect secret fails."""
    raw_payload = b'{"event":"order.paid"}'
    sig = hmac.new(b"wrong_secret", raw_payload, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(raw_payload, sig, "correct_secret") is False


def test_missing_signature_header():
    """Missing or empty signature header must return False."""
    assert verify_webhook_signature(b'{"test":1}', "", "secret") is False
    assert verify_webhook_signature(b'{"test":1}', None, "secret") is False


def test_extract_event_id():
    """Verify case-insensitive extraction of X-Razorpay-Event-Id."""
    assert extract_event_id({"X-Razorpay-Event-Id": "evt_123"}) == "evt_123"
    assert extract_event_id({"x-razorpay-event-id": "evt_456"}) == "evt_456"
    assert extract_event_id({"Other-Header": "abc"}) is None
