"""Centralized Structured Logging Configuration & Information Hygiene for Phase 9.4.

Contract: observability-logging/v1
Guarantees:
1. Strict Information Hygiene: Automatically sanitizes secrets, Razorpay keys, signatures, tokens, auth headers, and internal economics (COGS, margins).
2. Log Injection Neutralization: Strips carriage returns and newlines from all string values.
3. Bounded Payloads: Truncates oversized string fields (> 1024 chars) to prevent log flooding.
4. Seamless ContextVar integration: Automatically merges request_id and correlation context.
"""

import re
from typing import Any, Dict, MutableMapping
import structlog

# Sensitive key patterns to redact automatically
_SENSITIVE_KEY_PATTERNS = {
    "secret", "key_secret", "razorpay_key", "api_key", "token", "access_token",
    "authorization", "signature", "webhook_signature", "password", "cookie",
    "cogs_paise", "gross_margin_percent", "margin_percent", "matrix_a", "vector_b",
    "theta", "model_weights"
}

_MAX_STRING_LENGTH = 1024


def sanitize_value(val: Any) -> Any:
    """Recursively sanitize, unescape, and bound a log field value."""
    if isinstance(val, str):
        # 1. Log Injection Neutralization: strip carriage returns and newlines
        cleaned = val.replace("\r", " ").replace("\n", " ")
        # 2. String Bounding
        if len(cleaned) > _MAX_STRING_LENGTH:
            return cleaned[:_MAX_STRING_LENGTH] + "...[TRUNCATED]"
        return cleaned
    elif isinstance(val, dict):
        return {
            k: ("[REDACTED]" if is_sensitive_key(k) else sanitize_value(v))
            for k, v in val.items()
        }
    elif isinstance(val, (list, tuple)):
        return [sanitize_value(item) for item in val]
    return val


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary key matches any sensitive pattern."""
    if not isinstance(key, str):
        return False
    lower = key.lower()
    for pattern in _SENSITIVE_KEY_PATTERNS:
        if pattern in lower:
            return True
    return False


def sensitive_data_filter_processor(
    logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog processor that enforces Information Hygiene on all emitted logs."""
    sanitized: Dict[str, Any] = {}
    for k, v in event_dict.items():
        if is_sensitive_key(k):
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = sanitize_value(v)
    return sanitized


def configure_structured_logging(json_output: bool = True) -> None:
    """Initialize structured logging configuration with security processors."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        sensitive_data_filter_processor,
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
