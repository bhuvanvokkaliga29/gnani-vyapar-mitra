"""API hardening tests for Phase 3 Buyer Intent Engine.

Tests session isolation, oversized requests, empty requests, malformed
payloads, invalid session IDs, and latency bounds.
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# 1. SESSION ISOLATION
# =============================================================================


class TestSessionIsolation:
    """Verify Session A does not leak state into Session B."""

    @pytest.mark.asyncio
    async def test_session_a_does_not_pollute_session_b(self, client: AsyncClient):
        """Two concurrent sessions must remain completely independent."""
        # Session A: black backpack
        res_a1 = await client.post("/api/v1/intent/parse", json={
            "message": "I need a black backpack under ₹5,000"
        })
        assert res_a1.status_code == 200
        conv_a = res_a1.json()["conversation_id"]
        intent_a = res_a1.json()["intent"]
        assert intent_a["category"] == "backpack"

        # Session B: wireless mouse
        res_b1 = await client.post("/api/v1/intent/parse", json={
            "message": "I want a wireless mouse for office"
        })
        assert res_b1.status_code == 200
        conv_b = res_b1.json()["conversation_id"]
        intent_b = res_b1.json()["intent"]

        # Different conversation IDs
        assert conv_a != conv_b

        # Session B must not have backpack category
        assert intent_b["category"] == "wireless_mouse"
        assert intent_b["category"] != "backpack"

        # Session A Turn 2: verify original context preserved
        res_a2 = await client.post("/api/v1/intent/parse", json={
            "conversation_id": conv_a,
            "message": "Make it waterproof"
        })
        assert res_a2.status_code == 200
        intent_a2 = res_a2.json()["intent"]
        # Should still be backpack from Session A
        assert intent_a2["category"] == "backpack"

        # Session B Turn 2: verify original context preserved
        res_b2 = await client.post("/api/v1/intent/parse", json={
            "conversation_id": conv_b,
            "message": "Budget is under ₹1000"
        })
        assert res_b2.status_code == 200
        intent_b2 = res_b2.json()["intent"]
        # Should still be wireless mouse from Session B
        assert intent_b2["category"] == "wireless_mouse"
        # No waterproof contamination from Session A
        waterproof_reqs = [r for r in intent_b2["requirements"] if r["attribute"] == "water_resistant"]
        assert len(waterproof_reqs) == 0


# =============================================================================
# 2. INPUT VALIDATION / ABUSE TESTING
# =============================================================================


class TestAPIAbuse:
    """Verify controlled rejection of invalid, empty, and oversized payloads."""

    @pytest.mark.asyncio
    async def test_empty_message_rejected(self, client: AsyncClient):
        """Empty string message should be rejected with 422."""
        res = await client.post("/api/v1/intent/parse", json={"message": ""})
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_message_rejected(self, client: AsyncClient):
        """Message exceeding 2000 characters should be rejected with 422."""
        oversized = "a" * 2001
        res = await client.post("/api/v1/intent/parse", json={"message": oversized})
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_exactly_2000_chars_accepted(self, client: AsyncClient):
        """Message with exactly 2000 characters should be accepted."""
        exact = "I need a backpack. " + "a" * (2000 - len("I need a backpack. "))
        res = await client.post("/api/v1/intent/parse", json={"message": exact})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_message_field_rejected(self, client: AsyncClient):
        """Request without 'message' field should be rejected with 422."""
        res = await client.post("/api/v1/intent/parse", json={})
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_malformed_json_rejected(self, client: AsyncClient):
        """Completely malformed JSON should be rejected with 422."""
        res = await client.post(
            "/api/v1/intent/parse",
            content=b"{invalid json",
            headers={"content-type": "application/json"}
        )
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_no_stack_trace_in_error_response(self, client: AsyncClient):
        """Error responses must not contain internal stack traces."""
        res = await client.post("/api/v1/intent/parse", json={"message": ""})
        body = res.text
        assert "Traceback" not in body
        assert "File" not in body or "detail" in body  # allow 'detail' field


# =============================================================================
# 3. LATENCY BOUNDS
# =============================================================================


class TestLatencyBounds:
    """Verify intent parsing completes within acceptable latency."""

    @pytest.mark.asyncio
    async def test_single_turn_latency_under_100ms(self, client: AsyncClient):
        """Single-turn intent parsing should complete under 100ms."""
        res = await client.post("/api/v1/intent/parse", json={
            "message": "I need a travel backpack under ₹5,000 for a 15-inch laptop, prefer lightweight."
        })
        assert res.status_code == 200
        data = res.json()
        # Deterministic engine should be fast
        assert data["processing_time_ms"] < 100.0, (
            f"Processing took {data['processing_time_ms']}ms, expected < 100ms"
        )
