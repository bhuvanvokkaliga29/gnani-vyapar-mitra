from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app
from services.learning.model_service import PolicyLearningModelService
from services.learning.model_errors import ConcurrentModelUpdateError
from domain.models import Merchant, PolicyMemoryRecord
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus
)
from services.memory.service import PolicyMemoryService


@pytest.fixture
async def seed_learning_merchants(db_session):
    m1 = Merchant(id="merch_learn_a", name="Learn Merchant A", currency="INR", status="ACTIVE")
    m2 = Merchant(id="merch_learn_b", name="Learn Merchant B", currency="INR", status="ACTIVE")
    db_session.add_all([m1, m2])
    await db_session.commit()
    return m1, m2


@pytest.mark.asyncio
async def test_cold_start_model_creation(db_session, seed_learning_merchants):
    """Verify cold start initialization in DB."""
    model, version = await PolicyLearningModelService.get_or_create_model(db_session, "merch_learn_a")
    assert model.merchant_id == "merch_learn_a"
    assert model.observation_count == 0
    assert version == 1

    # Fetch again, returns existing
    model2, version2 = await PolicyLearningModelService.get_or_create_model(db_session, "merch_learn_a")
    assert model2.merchant_id == "merch_learn_a"
    assert version2 == 1


@pytest.mark.asyncio
async def test_optimistic_locking_detects_lost_updates(db_session, seed_learning_merchants):
    """Verify that concurrent updates with stale versions raise ConcurrentModelUpdateError."""
    model, version = await PolicyLearningModelService.get_or_create_model(db_session, "merch_learn_a")
    
    # Successful update
    x = [0.0] * 19
    x[0] = 1.0
    model.update(x, 15000)
    new_version = await PolicyLearningModelService.save_model(db_session, model, expected_version=version)
    assert new_version == 2

    # Attempt to save with stale version (1)
    with pytest.raises(ConcurrentModelUpdateError):
        await PolicyLearningModelService.save_model(db_session, model, expected_version=1)


@pytest.mark.asyncio
async def test_rebuild_from_memory_excludes_superseded_records(db_session, seed_learning_merchants):
    """Rebuild must strictly evaluate is_current=True records and ignore superseded records."""
    # Seed 1: superseded record (ORDER_CREATED, 0 paise)
    e1 = PolicyLearningEvidence(
        evidence_id="evi_lms_1",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_learn_a",
        experiment_id="exp_lms_1",
        experiment_observation_id="obs_lms_1",
        scenario_id="scen_lms_1",
        policy_id="p_test",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test_mid",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.ORDER_CREATED,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=0,
        expected_contribution_paise=0,
        observed_revenue_paise=0,
        observed_contribution_paise=0,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key="k",
        idempotency_key="id_lms_1",
        observed_at=datetime.now(timezone.utc) - timedelta(hours=2)
    )
    # Seed 2: reconciling record (PAYMENT_SUCCESS, 175000 paise)
    e2 = PolicyLearningEvidence(
        evidence_id="evi_lms_2",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_learn_a",
        experiment_id="exp_lms_1",
        experiment_observation_id="obs_lms_2",
        scenario_id="scen_lms_1",
        policy_id="p_test",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test_mid",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=350000,
        expected_contribution_paise=175000,
        observed_revenue_paise=350000,
        observed_contribution_paise=175000,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key="k",
        idempotency_key="id_lms_2",
        observed_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )

    await PolicyMemoryService.record_observation(db_session, e1)
    await PolicyMemoryService.record_observation(db_session, e2, correction_reason="RECONCILIATION")

    # Rebuild
    res = await PolicyLearningModelService.rebuild_merchant_model(db_session, "merch_learn_a")
    # Observation count must be exactly 1 (the current effective record)!
    assert res.observation_count == 1

    # Predict candidate
    pred = await PolicyLearningModelService.predict_candidate(
        db_session,
        merchant_id="merch_learn_a",
        policy_id="p_test",
        buyer_context_key="bck_test_mid"
    )
    assert pred.predicted_contribution_paise > 0
    assert pred.observation_count == 1


@pytest.mark.asyncio
async def test_merchant_isolation(db_session, seed_learning_merchants):
    """Merchant A's model must not leak into or affect Merchant B's model."""
    m_a, _ = await PolicyLearningModelService.get_or_create_model(db_session, "merch_learn_a")
    m_b, _ = await PolicyLearningModelService.get_or_create_model(db_session, "merch_learn_b")

    x = [0.0] * 19
    x[0] = 1.0
    m_a.update(x, 50000)
    await PolicyLearningModelService.save_model(db_session, m_a, expected_version=1)

    # Merchant B model remains pristine at cold start
    m_b_fresh, _ = await PolicyLearningModelService.get_or_create_model(db_session, "merch_learn_b")
    assert m_b_fresh.observation_count == 0
    pred_b, _, _ = m_b_fresh.predict(x)
    assert pred_b == 0


@pytest.mark.asyncio
async def test_learning_model_api_endpoints(client, seed_learning_merchants):
    """Test /api/v1/learning/model endpoints (rebuild, predict, state)."""
    # 1. State
    res_state = await client.get("/api/v1/learning/model/state?merchant_id=merch_learn_a")
    assert res_state.status_code == 200
    data_state = res_state.json()
    assert data_state["merchant_id"] == "merch_learn_a"
    assert data_state["model_version"] == "learning-model/v1"
    assert data_state["dimension"] == 19

    # 2. Predict
    predict_payload = {
        "merchant_id": "merch_learn_a",
        "policy_id": "p_api_test",
        "policy_version": "merchant-policy/v1",
        "buyer_context_key": "bck_travel_mid"
    }
    res_pred = await client.post("/api/v1/learning/model/predict", json=predict_payload)
    assert res_pred.status_code == 200
    data_pred = res_pred.json()
    assert "predicted_contribution_paise" in data_pred
    assert "uncertainty" in data_pred
    assert "ucb_score_paise" in data_pred
    # Assert NO forbidden decision keys
    assert "recommended" not in data_pred
    assert "winner" not in data_pred
    assert "execute" not in data_pred

    # 3. Rebuild
    rebuild_payload = {
        "merchant_id": "merch_learn_a",
        "lambda_reg": 1.0,
        "alpha_paise": 10000
    }
    res_reb = await client.post("/api/v1/learning/model/rebuild", json=rebuild_payload)
    assert res_reb.status_code == 200
    assert res_reb.json()["merchant_id"] == "merch_learn_a"
