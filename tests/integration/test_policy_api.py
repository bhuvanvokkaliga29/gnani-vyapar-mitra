"""Integration tests for POST /api/v1/policy/generate endpoint."""

import pytest
from httpx import AsyncClient
from tests.fixtures.commerce_fixtures import build_test_commerce_context


@pytest.mark.asyncio
async def test_generate_policy_endpoint_with_in_memory_context(client: AsyncClient):
    """Test policy generation endpoint passing pre-built MerchantCommerceContext."""
    context = build_test_commerce_context()

    payload = {
        "merchant_id": "merch_atlas_travel",
        "intent": {
            "category": "travel_backpack",
            "budget": {
                "max_amount_paise": 600000,
                "currency": "INR",
                "budget_type": "MAX",
                "constraint_type": "HARD"
            },
            "requirements": [
                {"attribute": "laptop_size", "operator": "GTE", "value": 15.0, "unit": "inch", "importance": "required"}
            ],
            "preferences": [],
            "exclusions": [],
            "unknowns": [],
            "conflicts": [],
            "needs_clarification": False,
            "confidence": "HIGH"
        },
        "commerce_context": context.model_dump(mode="json")
    }

    res = await client.post("/api/v1/policy/generate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "proposal" in data
    assert "latency_ms" in data
    assert "audit_run_id" in data

    prop = data["proposal"]
    assert prop["merchant_id"] == "merch_atlas_travel"
    assert prop["policy_version"] == "merchant-policy/v1"
    assert prop["status"] == "APPROVED_FOR_EVALUATION"
    assert prop["total_candidates"] >= 2
    assert prop["selected_candidate"] is not None


@pytest.mark.asyncio
async def test_generate_policy_endpoint_missing_merchant(client: AsyncClient):
    """When merchant is not in DB and no context is supplied, return 404."""
    payload = {
        "merchant_id": "merch_nonexistent_999",
        "intent": {
            "category": "travel_backpack",
            "requirements": [],
            "preferences": [],
            "exclusions": [],
            "unknowns": [],
            "conflicts": [],
            "needs_clarification": False,
            "confidence": "HIGH"
        }
    }

    res = await client.post("/api/v1/policy/generate", json=payload)
    assert res.status_code == 404
