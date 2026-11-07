"""Unit tests for Phase 8.3 PolicyMemoryService."""

from datetime import datetime, timezone, timedelta
import pytest
from services.experiments.schemas import VariantType
from services.learning.schemas import (
    PolicyLearningEvidence,
    EvidenceSource,
    LearningOutcomeType,
    EvidenceQualityStatus
)
from services.reward.schemas import (
    PolicyOpportunityReward,
    RewardState
)
from services.memory.service import PolicyMemoryService
from services.memory.schemas import HistoricalObservationFilter
from services.memory.errors import MemoryTenantViolationError
from domain.models import Merchant


def make_evidence(
    idx: int,
    merchant_id: str = "merch_atlas",
    policy_id: str = "p_treat",
    contrib_paise: int = 50000,
    is_safe: bool = True
) -> PolicyLearningEvidence:
    return PolicyLearningEvidence(
        evidence_id=f"evi_mem_test_{idx}",
        evidence_version="merchant-learning/v1",
        merchant_id=merchant_id,
        experiment_id="exp_mem_01",
        experiment_observation_id=f"obs_mem_{idx}",
        scenario_id=f"scen_mem_{idx}",
        policy_id=policy_id,
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.SIMULATED,
        outcome_type=LearningOutcomeType.SIMULATED_SELECTION if is_safe else LearningOutcomeType.SIMULATED_SELECTION,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=contrib_paise * 2,
        expected_contribution_paise=contrib_paise,
        margin_percent=50.0 if is_safe else 10.0,
        evidence_status=EvidenceQualityStatus.VALID if is_safe else EvidenceQualityStatus.GUARDRAIL_FAILURE,
        learning_eligible=is_safe,
        aggregation_key=f"{merchant_id}:bck_test:{policy_id}:merchant-policy/v1",
        idempotency_key=f"idem_mem_{idx}",
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=idx)
    )


@pytest.mark.asyncio
async def test_memory_service_record_and_idempotency(db_session):
    """Test recording an observation into memory and verifying idempotent replay."""
    m = Merchant(id="merch_atlas", name="Atlas Travel Gear", currency="INR", status="ACTIVE")
    db_session.add(m)
    await db_session.commit()

    evi = make_evidence(1)

    # 1. First record
    mem1 = await PolicyMemoryService.record_observation(db_session, evi)
    assert mem1.memory_id.startswith("mem_")
    assert mem1.opportunity_id == "exp_mem_01:scen_mem_1:TREATMENT"
    assert mem1.reward_contribution_paise == 50000

    # 2. Idempotent replay with same evidence
    mem2 = await PolicyMemoryService.record_observation(db_session, evi)
    assert mem2.memory_id == mem1.memory_id
    assert mem2.idempotency_key == mem1.idempotency_key


@pytest.mark.asyncio
async def test_memory_service_tenant_isolation(db_session):
    """Test that Merchant B cannot access Merchant A's memory record."""
    m1 = Merchant(id="merch_atlas_a", name="Atlas A", currency="INR", status="ACTIVE")
    m2 = Merchant(id="merch_atlas_b", name="Atlas B", currency="INR", status="ACTIVE")
    db_session.add_all([m1, m2])
    await db_session.commit()

    evi_a = make_evidence(2, merchant_id="merch_atlas_a")
    mem_a = await PolicyMemoryService.record_observation(db_session, evi_a)

    # Merchant A can read its own memory
    rec = await PolicyMemoryService.get_observation(db_session, "merch_atlas_a", mem_a.memory_id)
    assert rec is not None

    # Merchant B is rejected with MemoryTenantViolationError
    with pytest.raises(MemoryTenantViolationError):
        await PolicyMemoryService.get_observation(db_session, "merch_atlas_b", mem_a.memory_id)


@pytest.mark.asyncio
async def test_memory_service_query_history_and_summary(db_session):
    """Test historical query ordering, pagination, and factual summary calculation."""
    m = Merchant(id="merch_atlas_sum", name="Atlas Summary", currency="INR", status="ACTIVE")
    db_session.add(m)
    await db_session.commit()

    # Record 3 observations: 2 safe conversions (₹500 each), 1 guardrail failure
    evi1 = make_evidence(11, merchant_id="merch_atlas_sum", contrib_paise=50000, is_safe=True)
    evi2 = make_evidence(12, merchant_id="merch_atlas_sum", contrib_paise=50000, is_safe=True)
    evi3 = make_evidence(13, merchant_id="merch_atlas_sum", contrib_paise=10000, is_safe=False)

    await PolicyMemoryService.record_observation(db_session, evi1)
    await PolicyMemoryService.record_observation(db_session, evi2)
    await PolicyMemoryService.record_observation(db_session, evi3)

    # Query history
    filter_params = HistoricalObservationFilter(
        merchant_id="merch_atlas_sum",
        policy_id="p_treat",
        limit=10,
        offset=0
    )
    history = await PolicyMemoryService.query_history(db_session, filter_params)
    assert history.total_count == 3
    assert len(history.items) == 3

    # Summary calculation
    summary = await PolicyMemoryService.get_policy_summary(db_session, "merch_atlas_sum", "p_treat")
    assert summary.total_opportunities == 3
    assert summary.eligible_opportunities == 3  # All 3 in denominator
    assert summary.guardrail_violations == 1
    assert summary.is_policy_admissible is False  # Guardrail failure present!
    assert summary.total_contribution_paise == 100000  # 50k + 50k + 0 (failure zeroed)
    # 100,000 / 3 = 33,333 paise
    assert summary.contribution_per_shopper_paise == 33333
