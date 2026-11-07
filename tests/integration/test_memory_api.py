"""Integration tests for Phase 8.3 Memory API router."""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from domain.models import Merchant, ExperimentRecord, ObservationRecord, LearningEvidenceRecord


@pytest.fixture
async def seed_memory_evidence(db_session):
    """Seed database with valid learning evidence records ready for memory ingestion."""
    m = Merchant(id="merch_atlas_mem", name="Atlas Travel Gear", currency="INR", status="ACTIVE")
    exp = ExperimentRecord(
        id="exp_mem_api",
        merchant_id="merch_atlas_mem",
        name="Memory Exp",
        control_policy_id="p_ctrl",
        treatment_policy_id="p_treat",
        control_proposal_snapshot={"merchant_id": "merch_atlas_mem"},
        treatment_proposal_snapshot={"merchant_id": "merch_atlas_mem"},
        hypothesis={"population_description": "P", "control_description": "C", "treatment_description": "T", "expected_direction": "HIGHER", "primary_metric": "M", "rationale": "R"},
        status="COMPLETED"
    )
    obs = ObservationRecord(
        id="obs_mem_api",
        experiment_id="exp_mem_api",
        scenario_id="scen_mem_01",
        variant="TREATMENT",
        outcome_type="SIMULATED",
        is_selected=True,
        revenue_paise=350000,
        contribution_paise=175000,
        margin_percent=50.0,
        guardrail_violations=[],
        idempotency_key="obs_mem_api_key"
    )
    evi = LearningEvidenceRecord(
        id="evi_mem_api_01",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas_mem",
        experiment_id="exp_mem_api",
        experiment_observation_id="obs_mem_api",
        scenario_id="scen_mem_01",
        policy_id="p_treat",
        policy_version="merchant-policy/v1",
        variant="TREATMENT",
        buyer_context_key="bck_test",
        source="SIMULATED",
        outcome_type="SIMULATED_SELECTION",
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=350000,
        expected_contribution_paise=175000,
        margin_percent=50.0,
        evidence_status="VALID",
        lifecycle_state="LEARNING_ELIGIBLE",
        learning_eligible=True,
        aggregation_key="merch_atlas_mem:bck_test:p_treat:merchant-policy/v1",
        idempotency_key="evi_mem_api_01_key",
        observed_at=datetime.now(timezone.utc)
    )
    db_session.add_all([m, exp, obs, evi])
    await db_session.commit()
    return evi


@pytest.mark.asyncio
async def test_memory_api_full_lifecycle(client: AsyncClient, seed_memory_evidence):
    """Integration test: Ingest evidence into memory, fetch by ID, list, and fetch factual summary."""
    evi = seed_memory_evidence

    # 1. Ingest evidence into memory
    res_record = await client.post(
        "/api/v1/memory/record",
        json={
            "evidence_id": evi.id,
            "merchant_id": "merch_atlas_mem"
        }
    )
    assert res_record.status_code == 201
    mem_data = res_record.json()
    assert mem_data["memory_version"] == "merchant-memory/v1"
    assert mem_data["reward_contribution_paise"] == 175000
    mem_id = mem_data["memory_id"]

    # 2. Fetch single record by ID
    res_get = await client.get(f"/api/v1/memory/{mem_id}?merchant_id=merch_atlas_mem")
    assert res_get.status_code == 200
    assert res_get.json()["memory_id"] == mem_id

    # 3. Query history list
    res_list = await client.get(
        f"/api/v1/memory?merchant_id=merch_atlas_mem&policy_id=p_treat&limit=10"
    )
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total_count"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["memory_id"] == mem_id

    # 4. Fetch policy summary
    res_summary = await client.get(
        f"/api/v1/memory/summary/policy?merchant_id=merch_atlas_mem&policy_id=p_treat"
    )
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert summary_data["total_opportunities"] == 1
    assert summary_data["eligible_opportunities"] == 1
    assert summary_data["total_contribution_paise"] == 175000
    assert summary_data["contribution_per_shopper_paise"] == 175000
    assert summary_data["is_policy_admissible"] is True
