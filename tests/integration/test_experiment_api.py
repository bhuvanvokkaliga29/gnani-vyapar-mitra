"""Integration tests for Phase 7 Controlled Policy Experiments API."""

import pytest
from httpx import AsyncClient
from domain.models import Merchant


@pytest.fixture
async def seed_merchant(db_session):
    """Seed demo merchant Atlas Travel Gear."""
    merchant = Merchant(
        id="merch_atlas_travel",
        name="Atlas Travel Gear",
        currency="INR",
        status="ACTIVE"
    )
    db_session.add(merchant)
    await db_session.commit()
    return merchant


@pytest.mark.asyncio
async def test_experiment_api_lifecycle(client: AsyncClient, seed_merchant):
    """Full lifecycle integration test: create, start, run population, and fetch result."""
    create_payload = {
        "merchant_id": "merch_atlas_travel",
        "name": "API Lifecycle Experiment",
        "control_policy_id": "prop_api_ctrl",
        "treatment_policy_id": "prop_api_treat",
        "population_scenarios": [f"scen_api_{i}" for i in range(12)],
        "hypothesis": {
            "population_description": "Target buyers",
            "control_description": "Single product baseline",
            "treatment_description": "Value bundle with pouch",
            "expected_direction": "HIGHER",
            "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
            "rationale": "Bundle increases AOV and margin"
        },
        "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
        "secondary_metrics": ["SELECTION_RATE", "AOV_PAISE"],
        "guardrails": [
            {
                "guardrail_type": "MIN_MARGIN_PERCENT",
                "threshold_value": 0.40,
                "description": "Min 40% margin"
            }
        ]
    }

    # 1. Create Experiment
    res_create = await client.post("/api/v1/experiments", json=create_payload)
    assert res_create.status_code == 201
    exp_data = res_create.json()
    exp_id = exp_data["experiment_id"]
    assert exp_data["status"] == "DRAFT"
    assert exp_data["experiment_version"] == "policy-experiment/v1"

    # 2. Get Experiment
    res_get = await client.get(f"/api/v1/experiments/{exp_id}?merchant_id=merch_atlas_travel")
    assert res_get.status_code == 200
    assert res_get.json()["experiment_id"] == exp_id

    # 3. Start Experiment
    res_start = await client.post(f"/api/v1/experiments/{exp_id}/start?merchant_id=merch_atlas_travel", json={})
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "RUNNING"

    # 4. Run Population
    intents = {
        f"scen_api_{i}": {
            "budget": {"max_amount_paise": 400000, "currency": "INR"},
            "requirements": [{"attribute": "laptop_size", "operator": "GTE", "value": 15.6}],
            "exclusions": [
                {"attribute": "material", "excluded_value": "leather"},
                {"attribute": "color", "excluded_value": "blue"}
            ]
        }
        for i in range(12)
    }
    res_run = await client.post(
        f"/api/v1/experiments/{exp_id}/run?merchant_id=merch_atlas_travel",
        json={"execute_test_mode_orders": False, "population_intents": intents}
    )
    assert res_run.status_code == 200
    run_result = res_run.json()
    assert run_result["result_version"] == "experiment-result/v1"
    assert run_result["status"] == "COMPLETED"
    assert run_result["evidence_status"] == "SUFFICIENT_EVIDENCE"
    assert run_result["winner"] in ["CONTROL", "TREATMENT"]

    # 5. Fetch Final Result
    res_res = await client.get(f"/api/v1/experiments/{exp_id}/result?merchant_id=merch_atlas_travel")
    assert res_res.status_code == 200
    assert res_res.json()["experiment_id"] == exp_id
    assert res_res.json()["status"] == "COMPLETED"
