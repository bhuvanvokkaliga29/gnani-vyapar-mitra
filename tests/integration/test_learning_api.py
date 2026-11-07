"""Integration tests for Phase 8.1 Learning Evidence API endpoints."""

import pytest
from httpx import AsyncClient
from domain.models import Merchant, ExperimentRecord, ObservationRecord


@pytest.fixture
async def seed_experiment_with_observations(db_session):
    """Seed merchant, completed experiment, and observations."""
    m = Merchant(id="merch_atlas_travel", name="Atlas Travel Gear", currency="INR", status="ACTIVE")
    exp = ExperimentRecord(
        id="exp_api_test",
        merchant_id="merch_atlas_travel",
        name="API Learning Exp",
        control_policy_id="p_ctrl",
        treatment_policy_id="p_treat",
        control_proposal_snapshot={"merchant_id": "merch_atlas_travel"},
        treatment_proposal_snapshot={"merchant_id": "merch_atlas_travel"},
        hypothesis={
            "population_description": "Target",
            "control_description": "Ctrl",
            "treatment_description": "Treat",
            "expected_direction": "HIGHER",
            "primary_metric": "EXPECTED_CONTRIBUTION_PER_SHOPPER",
            "rationale": "Rationale"
        },
        status="COMPLETED"
    )

    observations = [
        ObservationRecord(
            id=f"obs_api_{i}",
            experiment_id="exp_api_test",
            scenario_id=f"scen_api_{i}",
            variant="TREATMENT" if i % 2 == 1 else "CONTROL",
            outcome_type="SIMULATED",
            is_selected=(i % 2 == 1),
            revenue_paise=349900 if (i % 2 == 1) else 0,
            contribution_paise=179900 if (i % 2 == 1) else 0,
            margin_percent=51.41 if (i % 2 == 1) else 0.0,
            guardrail_violations=[],
            idempotency_key=f"obs_exp_api_test_scen_{i}"
        )
        for i in range(4)
    ]

    db_session.add_all([m, exp] + observations)
    await db_session.commit()
    return exp


@pytest.mark.asyncio
async def test_learning_evidence_api_lifecycle(client: AsyncClient, seed_experiment_with_observations):
    """Full lifecycle integration test: ingest experiment observations, list, and fetch by ID."""
    exp = seed_experiment_with_observations

    # 1. Ingest Experiment Observations
    res_ingest = await client.post(
        f"/api/v1/learning/evidence/ingest-experiment/{exp.id}?merchant_id=merch_atlas_travel"
    )
    assert res_ingest.status_code == 200
    evidence_list = res_ingest.json()
    assert len(evidence_list) == 4
    first_evi = evidence_list[0]
    assert first_evi["evidence_version"] == "merchant-learning/v1"
    assert first_evi["experiment_id"] == exp.id
    evi_id = first_evi["evidence_id"]

    # 2. List Evidence with Filters
    res_list = await client.get(
        "/api/v1/learning/evidence?merchant_id=merch_atlas_travel&learning_eligible_only=true"
    )
    assert res_list.status_code == 200
    listed = res_list.json()
    assert len(listed) >= 1
    assert all(item["learning_eligible"] is True for item in listed)

    # 3. Get Single Evidence by ID
    res_get = await client.get(
        f"/api/v1/learning/evidence/{evi_id}?merchant_id=merch_atlas_travel"
    )
    assert res_get.status_code == 200
    fetched = res_get.json()
    assert fetched["evidence_id"] == evi_id
    assert fetched["merchant_id"] == "merch_atlas_travel"
