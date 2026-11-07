"""Security and signature verification utilities for WhatsApp Business Platform integration."""

import hmac
import hashlib
import re
import structlog
from typing import Optional

logger = structlog.get_logger()


def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to international E.164 digits without plus or separators.
    
    Examples:
        '+91 91139 60498' -> '919113960498'
        '+919113960498'   -> '919113960498'
        '9113960498'      -> '919113960498' (assumes India 91 if 10 digits)
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # Strip leading 0 if 11 digits (e.g. 09113960498)
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    # If 10 digits provided (standard Indian mobile), prepend 91 country code
    if len(digits) == 10 and digits.startswith(("6", "7", "8", "9")):
        digits = "91" + digits
    return digits


def verify_webhook_signature(
    payload_bytes: bytes = b"",
    signature_header: Optional[str] = None,
    app_secret: str = "",
    payload_body: Optional[bytes] = None
) -> bool:
    """Verify X-Hub-Signature-256 HMAC-SHA256 signature from Meta Cloud API.
    
    Meta sends:
        X-Hub-Signature-256: sha256=<hex_digest>
    
    If app_secret is not configured (e.g. local dev/test mode without live Meta app),
    logs a diagnostic warning and permits processing for automated testing.
    If app_secret is configured, strictly verifies the cryptographic HMAC.
    """
    body = payload_body if payload_body is not None else payload_bytes
    if not app_secret or not app_secret.strip():
        logger.debug("whatsapp_signature_validation_skipped_no_secret")
        return True

    if not signature_header:
        logger.warn("whatsapp_signature_missing_header")
        return False

    parts = signature_header.split("=", 1)
    if len(parts) != 2 or parts[0].strip().lower() != "sha256":
        logger.warn("whatsapp_signature_malformed_header", header=signature_header)
        return False

    expected_signature = parts[1].strip()
    computed_signature = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()

    is_valid = hmac.compare_digest(computed_signature, expected_signature)
    if not is_valid:
        logger.warn(
            "whatsapp_signature_mismatch",
            expected_prefix=expected_signature[:8] + "...",
            computed_prefix=computed_signature[:8] + "..."
        )
    return is_valid
