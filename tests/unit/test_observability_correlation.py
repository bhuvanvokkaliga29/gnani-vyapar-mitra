"""Unit tests for Phase 9.4 Async Correlation and Context Propagation."""

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from services.observability.correlation import (
    generate_request_id,
    validate_request_id,
    set_correlation_context,
    reset_correlation_context,
    get_correlation_context,
    get_current_request_id,
    get_current_merchant_id,
)


def test_generate_request_id_format():
    """Verify generated request_id adheres to canonical format req_..."""
    rid = generate_request_id()
    assert rid.startswith("req_")
    assert len(rid) >= 20
    assert rid.replace("req_", "").isalnum()


def test_validate_request_id_sanitizes_injection():
    """Verify request_id validator strips illegal characters and log injection attempts."""
    # Malicious injection attempt with newlines and forged log fields
    malicious = "req_12345\r\n{\"event\":\"fake.event\",\"admin\":true}\n"
    cleaned = validate_request_id(malicious)
    assert "\r" not in cleaned
    assert "\n" not in cleaned
    assert "{" not in cleaned
    assert "}" not in cleaned
    assert cleaned.startswith("req_12345")

    # None or empty produces clean canonical ID
    assert validate_request_id(None).startswith("req_")
    assert validate_request_id("").startswith("req_")

    # Oversized string produces safe ID
    oversized = "a" * 100
    assert len(validate_request_id(oversized)) <= 64


@pytest.mark.asyncio
async def test_contextvars_async_isolation_concurrent_tasks():
    """Verify ContextVar correlation context never leaks between concurrent async tasks."""
    results = {}

    async def worker(tenant_id: str, req_id: str, delay: float):
        token = set_correlation_context(
            request_id=req_id,
            merchant_id=tenant_id,
            opportunity_id=f"opp_{tenant_id}"
        )
        try:
            await asyncio.sleep(delay)
            # Verify context remained pristine and uncorrupted by concurrent coroutines
            ctx = get_correlation_context()
            results[tenant_id] = {
                "request_id": get_current_request_id(),
                "merchant_id": get_current_merchant_id(),
                "opportunity_id": ctx.get("opportunity_id"),
            }
        finally:
            reset_correlation_context(token)

    # Launch 5 concurrent workers interleaved with different delays
    tasks = [
        worker("merch_alpha", "req_alpha_001", 0.05),
        worker("merch_beta", "req_beta_002", 0.02),
        worker("merch_gamma", "req_gamma_003", 0.04),
        worker("merch_delta", "req_delta_004", 0.01),
        worker("merch_epsilon", "req_epsilon_005", 0.03),
    ]
    await asyncio.gather(*tasks)

    # Assert 100% strict isolation
    assert results["merch_alpha"]["request_id"] == "req_alpha_001"
    assert results["merch_alpha"]["merchant_id"] == "merch_alpha"
    assert results["merch_beta"]["request_id"] == "req_beta_002"
    assert results["merch_beta"]["merchant_id"] == "merch_beta"
    assert results["merch_gamma"]["request_id"] == "req_gamma_003"
    assert results["merch_gamma"]["merchant_id"] == "merch_gamma"
    assert results["merch_delta"]["request_id"] == "req_delta_004"
    assert results["merch_delta"]["merchant_id"] == "merch_delta"
    assert results["merch_epsilon"]["request_id"] == "req_epsilon_005"
    assert results["merch_epsilon"]["merchant_id"] == "merch_epsilon"


@pytest.mark.asyncio
async def test_correlation_middleware_header_propagation():
    """Verify CorrelationMiddleware propagates X-Request-ID in response headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Client provides valid X-Request-ID
        res1 = await client.get("/health", headers={"X-Request-ID": "req_client_trace_42"})
        assert res1.status_code == 200
        assert res1.headers.get("X-Request-ID") == "req_client_trace_42"

        # Case 2: Client provides no header -> server generates safe req_...
        res2 = await client.get("/health")
        assert res2.status_code == 200
        generated = res2.headers.get("X-Request-ID")
        assert generated is not None
        assert generated.startswith("req_")
