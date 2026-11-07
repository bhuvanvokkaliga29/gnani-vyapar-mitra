"""Unit tests for configuration validation and secret protection."""

import pytest
from apps.api.core.config import Settings


def test_config_defaults():
    """Verify default configuration loads cleanly."""
    cfg = Settings()
    assert cfg.APP_ENV == "development"
    assert cfg.RAZORPAY_KEY_ID.startswith("rzp_test_")


def test_sanitized_dict_masks_secrets():
    """Verify secrets are masked and never exposed in sanitized output."""
    cfg = Settings(
        RAZORPAY_KEY_SECRET="super_secret_key_123",
        RAZORPAY_WEBHOOK_SECRET="webhook_secret_abc"
    )
    sanitized = cfg.sanitized_dict()

    assert sanitized["RAZORPAY_KEY_SECRET"] == "******"
    assert sanitized["RAZORPAY_WEBHOOK_SECRET"] == "******"
    assert "super_secret_key_123" not in str(sanitized)


def test_live_key_prevention():
    """Verify that live keys are rejected in test environments."""
    with pytest.raises(ValueError, match="Live Razorpay keys are prohibited"):
        Settings(RAZORPAY_KEY_ID="rzp_live_abc123456")
