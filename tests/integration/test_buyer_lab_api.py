"""Integration tests for POST /api/v1/buyer-lab/simulate API endpoint."""

import pytest
from httpx import AsyncClient
from apps.api.main import app
from domain.intent_schemas import BuyerIntent, BudgetConstraint, AttributeRequirement, OperatorType
from services.buyer_lab.schemas import BuyerOffer


@pytest.mark.asyncio
async def test_simulate_api_winning_selection(client: AsyncClient):
    """POST /api/v1/buyer-lab/simulate returns winning selection and structured audit trace."""
    intent = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=400000, currency="INR"),
        requirements=[AttributeRequirement(attribute="laptop_size", operator=OperatorType.GTE, value=15.6)]
    )

    offers = [
        BuyerOffer(
            offer_id="off_atlas",
            merchant_id="merch_atlas",
            merchant_label="Atlas Travel Gear",
            product_id="prod_1",
            product_name="Atlas Pack",
            price_paise=299900,
            currency="INR",
            availability=True,
            relevant_attributes={"laptop_size": 15.6}
        ),
        BuyerOffer(
            offer_id="off_cheap_small",
            merchant_id="merch_budget",
            merchant_label="Budget Packs",
            product_id="prod_2",
            product_name="Small Pack",
            price_paise=150000,
            currency="INR",
            availability=True,
            relevant_attributes={"laptop_size": 14.0}  # Fails 15.6!
        )
    ]

    payload = {
        "intent": intent.model_dump(mode="json"),
        "offers": [o.model_dump(mode="json") for o in offers],
        "scenario_id": "test_api_01",
        "buyer_persona": "BALANCED"
    }

    res = await client.post("/api/v1/buyer-lab/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["simulation_id"].startswith("sim_")
    assert data["execution_time_ms"] > 0
    result = data["result"]
    assert result["result_version"] == "buyer-selection/v1"
    assert result["selected_offer_id"] == "off_atlas"
    assert len(result["rejected_offers"]) == 1
    assert result["rejected_offers"][0]["offer_id"] == "off_cheap_small"
    assert result["rejected_offers"][0]["rejection_reason"] == "HARD_REQUIREMENT_VIOLATED"


@pytest.mark.asyncio
async def test_simulate_api_no_eligible_offer(client: AsyncClient):
    """POST /api/v1/buyer-lab/simulate returns NO_ELIGIBLE_OFFER when all offers exceed budget."""
    intent = BuyerIntent(
        budget=BudgetConstraint(max_amount_paise=100000, currency="INR")
    )

    offers = [
        BuyerOffer(
            offer_id="off_over_budget",
            merchant_id="merch_atlas",
            merchant_label="Atlas Gear",
            product_id="prod_1",
            product_name="Atlas Pack",
            price_paise=299900,
            currency="INR",
            availability=True
        )
    ]

    payload = {
        "intent": intent.model_dump(mode="json"),
        "offers": [o.model_dump(mode="json") for o in offers],
        "scenario_id": "test_api_no_offer"
    }

    res = await client.post("/api/v1/buyer-lab/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    result = data["result"]

    assert result["selected_offer_id"] is None
    assert "NO_ELIGIBLE_OFFER" in result["selection_reasons"]
    assert len(result["eligible_offer_ids"]) == 0
    assert len(result["rejected_offers"]) == 1
    assert result["rejected_offers"][0]["rejection_reason"] == "BUDGET_EXCEEDED"
