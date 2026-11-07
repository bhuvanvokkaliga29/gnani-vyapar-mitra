"""Unit tests for Phase 9.4 Structured Logging Hygiene and Information Hygiene."""

from apps.api.core.logging import (
    sanitize_value,
    is_sensitive_key,
    sensitive_data_filter_processor,
)


def test_sensitive_key_detection():
    """Verify sensitive key detector catches secrets, tokens, signatures, and internal economics."""
    assert is_sensitive_key("razorpay_key_secret") is True
    assert is_sensitive_key("api_key") is True
    assert is_sensitive_key("access_token") is True
    assert is_sensitive_key("webhook_signature") is True
    assert is_sensitive_key("authorization") is True
    assert is_sensitive_key("password") is True
    assert is_sensitive_key("cogs_paise") is True
    assert is_sensitive_key("gross_margin_percent") is True
    assert is_sensitive_key("matrix_a") is True
    assert is_sensitive_key("vector_b") is True

    # Safe keys are not flagged
    assert is_sensitive_key("merchant_id") is False
    assert is_sensitive_key("opportunity_id") is False
    assert is_sensitive_key("decision_id") is False
    assert is_sensitive_key("execution_id") is False
    assert is_sensitive_key("status") is False


def test_sanitize_value_redacts_nested_secrets_and_economics():
    """Verify recursive sanitization replaces sensitive dictionary values with [REDACTED]."""
    payload = {
        "merchant_id": "merch_alpha",
        "api_key": "rzp_live_secret12345",
        "details": {
            "cogs_paise": 250000,
            "margin_percent": 35.5,
            "product_name": "Backpack",
            "auth": {
                "token": "bearer_super_secret"
            }
        }
    }

    sanitized = sanitize_value(payload)
    assert sanitized["merchant_id"] == "merch_alpha"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["details"]["cogs_paise"] == "[REDACTED]"
    assert sanitized["details"]["margin_percent"] == "[REDACTED]"
    assert sanitized["details"]["product_name"] == "Backpack"
    assert sanitized["details"]["auth"]["token"] == "[REDACTED]"


def test_log_injection_neutralization():
    """Verify log injection attacks with newline characters are stripped into single-line strings."""
    malicious_input = "User input\r\n{\"event\":\"forged.admin.action\",\"level\":\"critical\"}\nNormal trailing"
    cleaned = sanitize_value(malicious_input)
    assert "\r" not in cleaned
    assert "\n" not in cleaned
    assert "User input  {\"event\":\"forged.admin.action\"" in cleaned


def test_payload_bounding_truncates_oversized_strings():
    """Verify strings longer than 1024 characters are truncated to prevent log flooding."""
    huge_str = "x" * 2000
    bounded = sanitize_value(huge_str)
    assert len(bounded) <= 1024 + len("...[TRUNCATED]")
    assert bounded.endswith("...[TRUNCATED]")


def test_structlog_processor_integration():
    """Verify sensitive_data_filter_processor scrubs event_dict in place."""
    event_dict = {
        "event": "execution.authorized",
        "merchant_id": "merch_alpha",
        "key_secret": "rzp_secret_999",
        "cogs_paise": 150000,
        "notes": "Safe text\r\nInjected line",
        "level": "info"
    }
    processed = sensitive_data_filter_processor(None, "info", event_dict)
    assert processed["key_secret"] == "[REDACTED]"
    assert processed["cogs_paise"] == "[REDACTED]"
    assert "\r" not in processed["notes"]
    assert "\n" not in processed["notes"]
    assert processed["merchant_id"] == "merch_alpha"
