"""Webhook Verification and Parsing for Razorpay Adapter."""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from services.razorpay.errors import RazorpaySignatureVerificationError
from services.razorpay.models import RazorpayWebhookPayload


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    webhook_secret: str
) -> bool:
    """Verify inbound Razorpay webhook signature using HMAC SHA-256 with constant-time comparison."""
    if not signature_header or not webhook_secret or not raw_body:
        return False

    expected_signature = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature.lower(), signature_header.lower())


def extract_event_id(headers: Dict[str, str]) -> Optional[str]:
    """Extract X-Razorpay-Event-Id header case-insensitively."""
    for k, v in headers.items():
        if k.lower() == "x-razorpay-event-id":
            return v
    return None


def parse_webhook_payload(raw_body: bytes) -> RazorpayWebhookPayload:
    """Parse raw bytes into a typed RazorpayWebhookPayload."""
    try:
        data = json.loads(raw_body.decode("utf-8"))
        return RazorpayWebhookPayload.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid JSON in webhook payload: {str(exc)}") from exc
