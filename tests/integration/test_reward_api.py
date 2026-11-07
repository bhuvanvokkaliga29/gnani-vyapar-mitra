"""Integration tests for Phase 8.2 Reward API router."""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from domain.models import Merchant, ExperimentRecord, ObservationRecord, LearningEvidenceRecord


@pytest.fixture
async def seed_reward_evidence(db_session):
    """Seed database with valid learning evidence records ready for reward evaluation."""
    m = Merchant(id="merch_atlas_travel", name="Atlas Travel Gear", currency="INR", status="ACTIVE")
    exp = ExperimentRecord(
        id="exp_rwd_test",
        merchant_id="merch_atlas_travel",
        name="Reward Exp",
        control_policy_id="p_ctrl",
        treatment_policy_id="p_treat",
        control_proposal_snapshot={"merchant_id": "merch_atlas_travel"},
        treatment_proposal_snapshot={"merchant_id": "merch_atlas_travel"},
        hypothesis={"population_description": "P", "control_description": "C", "treatment_description": "T", "expected_direction": "HIGHER", "primary_metric": "M", "rationale": "R"},
        status="COMPLETED"
    )
    obs = ObservationRecord(
        id="obs_rwd_test",
        experiment_id="exp_rwd_test",
        scenario_id="scen_rwd_01",
        variant="TREATMENT",
        outcome_type="SIMULATED",
        is_selected=True,
        revenue_paise=350000,
        contribution_paise=175000,
        margin_percent=50.0,
        guardrail_violations=[],
        idempotency_key="obs_rwd_test_key"
    )
    evi = LearningEvidenceRecord(
        id="evi_rwd_test_01",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_atlas_travel",
        experiment_id="exp_rwd_test",
        experiment_observation_id="obs_rwd_test",
        scenario_id="scen_rwd_01",
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
        aggregation_key="merch_atlas_travel:bck_test:p_treat:merchant-policy/v1",
        idempotency_key="evi_rwd_test_01_key",
        observed_at=datetime.now(timezone.utc)
    )
    db_session.add_all([m, exp, obs, evi])
    await db_session.commit()
    return evi


@pytest.mark.asyncio
async def test_reward_api_evaluate_and_aggregate(client: AsyncClient, seed_reward_evidence):
    """Integration test: Evaluate single evidence reward and aggregate across policy opportunities."""
    evi = seed_reward_evidence

    # 1. Evaluate single evidence
    res_single = await client.post(
        f"/api/v1/reward/evaluate-evidence/{evi.id}?merchant_id=merch_atlas_travel"
    )
    assert res_single.status_code == 200
    rwd_data = res_single.json()
    assert rwd_data["reward_version"] == "merchant-reward/v1"
    assert rwd_data["reward_state"] == "REWARD_ELIGIBLE"
    assert rwd_data["reward_contribution_paise"] == 175000

    # 2. Aggregate across policy
    res_agg = await client.post(
        "/api/v1/reward/aggregate",
        json={
            "merchant_id": "merch_atlas_travel",
            "policy_id": "p_treat"
        }
    )
    assert res_agg.status_code == 200
    agg_data = res_agg.json()
    assert agg_data["objective_version"] == "merchant-reward/v1"
    assert agg_data["eligible_opportunity_count"] == 1
    assert agg_data["total_contribution_paise"] == 175000
    assert agg_data["contribution_per_shopper_paise"] == 175000
