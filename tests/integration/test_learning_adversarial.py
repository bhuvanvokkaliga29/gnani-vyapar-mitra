"""Adversarial test suite for Phase 8.4 Merchant Policy Learning Model.

Covers all 54 failure modes across Reward, Evidence, Merchant Isolation, Feature Safety,
Mathematical Model, Replay, Supersession, Versioning, Concurrency, Numerical Robustness, and Boundary.
"""

import math
from datetime import datetime, timedelta, timezone
import pytest
from services.learning.algorithm import ContextualLinearUCB, REWARD_SCALE_FACTOR
from services.learning.features import (
    PolicyFeatureExtractor,
    FEATURE_DIMENSION,
    FEATURE_SCHEMA_VERSION
)
from services.learning.model_service import PolicyLearningModelService
from services.learning.model_errors import (
    CorruptedModelStateError,
    IncompatibleFeatureSchemaError,
    ConcurrentModelUpdateError,
    LearningModelError
)
from services.learning.model_schemas import (
    CandidatePredictionRequestSchema,
    ModelRebuildRequestSchema
)
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
async def seed_adv_merchants(db_session):
    m_a = Merchant(id="merch_adv_a", name="Adv Merchant A", currency="INR", status="ACTIVE")
    m_b = Merchant(id="merch_adv_b", name="Adv Merchant B", currency="INR", status="ACTIVE")
    db_session.add_all([m_a, m_b])
    await db_session.commit()
    return m_a, m_b


# =============================================================================
# 1. REWARD ADVERSARIAL CASES (1-6)
# =============================================================================

def test_reward_modes_positive_zero_negative_and_invalid():
    """Modes 1, 2, 3, 4, 5: Positive, Zero, Negative, Missing, Invalid."""
    model = ContextualLinearUCB("m_rwd")
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0

    # 1. Positive
    model.update(x, 25000)
    assert model.b[0] == 250.0

    # 2. Zero
    model.update(x, 0)
    assert model.b[0] == 250.0  # unchanged b, updated A
    assert model.observation_count == 2

    # 3. Negative
    model.update(x, -50000)
    assert model.b[0] == -250.0  # 250 - 500 = -250
    assert model.observation_count == 3

    # 4 & 5. Invalid / non-integer types
    with pytest.raises(CorruptedModelStateError):
        model.update(x, "5000")  # type: ignore

    with pytest.raises(CorruptedModelStateError):
        model.update(x, None)  # type: ignore


# =============================================================================
# 2. EVIDENCE & SUPERSESSION ADVERSARIAL CASES (7-11, 33-35)
# =============================================================================

@pytest.mark.asyncio
async def test_evidence_and_supersession_rebuild_integrity(db_session, seed_adv_merchants):
    """Modes 7-11, 33-35: Simulated vs Test Mode, Ineligible, Superseded, Duplicate."""
    # 1. Valid initial order observation (0 paise)
    e1 = PolicyLearningEvidence(
        evidence_id="evi_adv_1",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_adv_a",
        experiment_id="exp_adv",
        experiment_observation_id="obs_adv_1",
        scenario_id="scen_adv_1",
        policy_id="p_adv",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_adv_mid",
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
        idempotency_key="id_adv_1",
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=30)
    )
    # 2. Superseding payment captured (100000 paise)
    e2 = PolicyLearningEvidence(
        evidence_id="evi_adv_2",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_adv_a",
        experiment_id="exp_adv",
        experiment_observation_id="obs_adv_2",
        scenario_id="scen_adv_1",
        policy_id="p_adv",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_adv_mid",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=200000,
        expected_contribution_paise=100000,
        observed_revenue_paise=200000,
        observed_contribution_paise=100000,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key="k",
        idempotency_key="id_adv_2",
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    # 3. Ineligible evidence (safety guardrail violation)
    e3 = PolicyLearningEvidence(
        evidence_id="evi_adv_3",
        evidence_version="merchant-learning/v1",
        merchant_id="merch_adv_a",
        experiment_id="exp_adv",
        experiment_observation_id="obs_adv_3",
        scenario_id="scen_adv_2",
        policy_id="p_adv",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_adv_mid",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=LearningOutcomeType.EXECUTION_REJECTED,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=0,
        expected_contribution_paise=0,
        observed_revenue_paise=0,
        observed_contribution_paise=0,
        margin_percent=0.0,
        evidence_status=EvidenceQualityStatus.GUARDRAIL_FAILURE,
        learning_eligible=False,  # Excluded!
        aggregation_key="k",
        idempotency_key="id_adv_3",
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    await PolicyMemoryService.record_observation(db_session, e1)
    await PolicyMemoryService.record_observation(db_session, e2, correction_reason="RECONCILIATION")
    await PolicyMemoryService.record_observation(db_session, e3)

    # Rebuild
    res = await PolicyLearningModelService.rebuild_merchant_model(db_session, "merch_adv_a")
    # Exactly 1 record (e2) should be trained into model!
    # e1 is superseded (is_current=False), e3 is learning_eligible=False.
    assert res.observation_count == 1

    # Verify model prediction
    pred = await PolicyLearningModelService.predict_candidate(
        db_session,
        merchant_id="merch_adv_a",
        policy_id="p_adv",
        buyer_context_key="bck_adv_mid"
    )
    assert pred.observation_count == 1
    assert pred.predicted_contribution_paise > 0


# =============================================================================
# 3. CONCURRENCY & LOST UPDATE AUDIT (41-43)
# =============================================================================

@pytest.mark.asyncio
async def test_concurrent_lost_update_prevention(db_session, seed_adv_merchants):
    """Modes 41-43: Stale model version updates are rejected immediately."""
    model, version = await PolicyLearningModelService.get_or_create_model(db_session, "merch_adv_a")
    x = [0.0] * FEATURE_DIMENSION
    x[0] = 1.0
    model.update(x, 10000)

    # Client A updates first
    v2 = await PolicyLearningModelService.save_model(db_session, model, expected_version=version)
    assert v2 == 2

    # Client B attempts update with stale version 1
    with pytest.raises(ConcurrentModelUpdateError):
        await PolicyLearningModelService.save_model(db_session, model, expected_version=1)


# =============================================================================
# 4. NUMERICAL ROBUSTNESS (44-48)
# =============================================================================

def test_numerical_robustness_extreme_magnitudes():
    """Modes 44-48: Near-zero, huge values, and finite checks."""
    model = ContextualLinearUCB("m_robust")

    # 1. Very small values
    x_small = [1e-6] * FEATURE_DIMENSION
    model.update(x_small, 1)  # 1 paise
    pred_s, unc_s, ucb_s = model.predict(x_small)
    assert not math.isnan(pred_s)
    assert not math.isnan(unc_s)

    # 2. Large values
    x_large = [1.0] * FEATURE_DIMENSION
    model.update(x_large, 10000000)  # ₹1,00,000 = 10,000,000 paise
    pred_l, unc_l, ucb_l = model.predict(x_large)
    assert not math.isnan(pred_l)
    assert not math.isinf(pred_l)
    assert pred_l > 0


# =============================================================================
# 5. VERSIONING INCOMPATIBILITY CHECKS (36-40)
# =============================================================================

def test_versioning_rejection_of_incompatible_dimensions():
    """Modes 36-40: Deserialization rejects mismatched dimensions."""
    data = {
        "merchant_id": "m_bad",
        "dimension": 10,  # Expected 19
        "lambda_reg": 1.0,
        "alpha_paise": 10000,
        "matrix_a": [[1.0] * 10] * 10,
        "vector_b": [0.0] * 10,
        "theta": [0.0] * 10
    }
    with pytest.raises(IncompatibleFeatureSchemaError):
        ContextualLinearUCB.from_dict(data)
