"""Integration tests for Phase 8.3 Refinement: Reconciliation & Historical Memory Integrity."""

from datetime import datetime, timedelta, timezone
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


def make_reconciliation_evidence(
    evidence_id: str,
    outcome_type: LearningOutcomeType,
    revenue_paise: int,
    contrib_paise: int,
    merchant_id: str = "merch_recon",
    opportunity_id: str = "exp_recon_01:scen_01:TREATMENT"
) -> PolicyLearningEvidence:
    """Helper to create evidence records for reconciliation lifecycle testing."""
    return PolicyLearningEvidence(
        evidence_id=evidence_id,
        evidence_version="merchant-learning/v1",
        merchant_id=merchant_id,
        experiment_id="exp_recon_01",
        experiment_observation_id=f"obs_{evidence_id}",
        scenario_id="scen_01",
        policy_id="p_treat",
        variant=VariantType.TREATMENT,
        buyer_context_key="bck_test",
        source=EvidenceSource.TEST_MODE_OBSERVED,
        outcome_type=outcome_type,
        sample_size=1,
        is_selected=True,
        expected_revenue_paise=revenue_paise,
        expected_contribution_paise=contrib_paise,
        observed_revenue_paise=revenue_paise,
        observed_contribution_paise=contrib_paise,
        margin_percent=50.0,
        evidence_status=EvidenceQualityStatus.VALID,
        learning_eligible=True,
        aggregation_key=f"{merchant_id}:bck_test:p_treat:merchant-policy/v1",
        idempotency_key=f"idem_{evidence_id}",
        observed_at=datetime.now(timezone.utc)
    )


@pytest.fixture
async def seed_recon_merchant(db_session):
    m = Merchant(id="merch_recon", name="Recon Merchant", currency="INR", status="ACTIVE")
    m_other = Merchant(id="merch_recon_other", name="Other Recon Merchant", currency="INR", status="ACTIVE")
    db_session.add_all([m, m_other])
    await db_session.commit()
    return m


@pytest.mark.asyncio
async def test_case_a_order_created_to_payment_captured(db_session, seed_recon_merchant):
    """Case A: Order created -> Later payment captured.
    
    Verifies that the original record is preserved immutably with is_current=False and superseded_by,
    while the new record is is_current=True and supersedes the old record.
    """
    # 1. Initial observation: ORDER_CREATED
    e_order = make_reconciliation_evidence(
        evidence_id="evi_order_created_1",
        outcome_type=LearningOutcomeType.ORDER_CREATED,
        revenue_paise=0,
        contrib_paise=0
    )
    mem1 = await PolicyMemoryService.record_observation(db_session, e_order)
    assert mem1.is_current is True
    assert mem1.supersedes is None
    assert mem1.superseded_by is None
    assert mem1.reward_contribution_paise == 0

    # 2. Authoritative reconciliation: PAYMENT_CAPTURED
    e_paid = make_reconciliation_evidence(
        evidence_id="evi_payment_captured_1",
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        revenue_paise=350000,
        contrib_paise=175000
    )
    mem2 = await PolicyMemoryService.record_observation(
        db_session,
        e_paid,
        correction_reason="RECONCILIATION_PAYMENT_CAPTURED",
        reconciliation_ref="evt_pay_captured_123"
    )

    # Re-fetch original record to verify immutability and linkage
    mem1_updated = await PolicyMemoryService.get_observation(db_session, "merch_recon", mem1.memory_id)
    assert mem1_updated.is_current is False
    assert mem1_updated.superseded_by == mem2.memory_id
    # Original historical figures remain completely intact!
    assert mem1_updated.reward_contribution_paise == 0
    assert mem1_updated.outcome_type == LearningOutcomeType.ORDER_CREATED

    # Verify new record
    assert mem2.is_current is True
    assert mem2.supersedes == mem1.memory_id
    assert mem2.superseded_by is None
    assert mem2.correction_reason == "RECONCILIATION_PAYMENT_CAPTURED"
    assert mem2.reconciliation_ref == "evt_pay_captured_123"
    assert mem2.reward_contribution_paise == 175000


@pytest.mark.asyncio
async def test_case_b_order_created_to_payment_failed(db_session, seed_recon_merchant):
    """Case B: Order created -> Later payment failed."""
    e_order = make_reconciliation_evidence(
        evidence_id="evi_order_created_2",
        outcome_type=LearningOutcomeType.ORDER_CREATED,
        revenue_paise=0,
        contrib_paise=0,
        opportunity_id="exp_recon_01:scen_02:TREATMENT"
    )
    mem1 = await PolicyMemoryService.record_observation(db_session, e_order)

    e_failed = make_reconciliation_evidence(
        evidence_id="evi_payment_failed_2",
        outcome_type=LearningOutcomeType.PAYMENT_FAILURE,
        revenue_paise=0,
        contrib_paise=0,
        opportunity_id="exp_recon_01:scen_02:TREATMENT"
    )
    mem2 = await PolicyMemoryService.record_observation(
        db_session,
        e_failed,
        correction_reason="RECONCILIATION_PAYMENT_FAILED"
    )

    mem1_up = await PolicyMemoryService.get_observation(db_session, "merch_recon", mem1.memory_id)
    assert mem1_up.is_current is False
    assert mem1_up.superseded_by == mem2.memory_id
    assert mem2.is_current is True
    assert mem2.supersedes == mem1.memory_id


@pytest.mark.asyncio
async def test_cases_d_and_e_webhook_and_reconciliation_replay_idempotent(db_session, seed_recon_merchant):
    """Cases D & E: Webhook or reconciliation event replayed -> Idempotent, no extra rows."""
    e_paid = make_reconciliation_evidence(
        evidence_id="evi_pay_replay_3",
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        revenue_paise=200000,
        contrib_paise=100000,
        opportunity_id="exp_recon_01:scen_03:TREATMENT"
    )

    mem1 = await PolicyMemoryService.record_observation(db_session, e_paid)
    mem2 = await PolicyMemoryService.record_observation(db_session, e_paid)

    assert mem1.memory_id == mem2.memory_id
    assert mem1.idempotency_key == mem2.idempotency_key


@pytest.mark.asyncio
async def test_double_counting_prevention_in_summary_metrics(db_session, seed_recon_merchant):
    """Refinement Core: Verify that an opportunity with 2 lifecycle events does NOT double-count.
    
    1 Opportunity with (ORDER_CREATED -> PAYMENT_CAPTURED):
    - Current effective summary must count total_opportunities = 1, eligible_opportunities = 1, total_contribution_paise = 175000.
    - Raw historical summary must count total_opportunities = 2 for audit.
    """
    opp_id = "exp_recon_01:scen_double_check:TREATMENT"
    e1 = make_reconciliation_evidence(
        evidence_id="evi_dc_order",
        outcome_type=LearningOutcomeType.ORDER_CREATED,
        revenue_paise=0,
        contrib_paise=0,
        opportunity_id=opp_id
    )
    e2 = make_reconciliation_evidence(
        evidence_id="evi_dc_paid",
        outcome_type=LearningOutcomeType.PAYMENT_SUCCESS,
        revenue_paise=350000,
        contrib_paise=175000,
        opportunity_id=opp_id
    )

    await PolicyMemoryService.record_observation(db_session, e1)
    await PolicyMemoryService.record_observation(db_session, e2)

    # 1. Current Effective Summary (Default View)
    summary_effective = await PolicyMemoryService.get_policy_summary(
        db_session,
        merchant_id="merch_recon",
        policy_id="p_treat",
        is_current_only=True
    )
    assert summary_effective.evaluation_view == "CURRENT_EFFECTIVE"
    assert summary_effective.total_opportunities == 1  # Exactly 1!
    assert summary_effective.eligible_opportunities == 1
    assert summary_effective.total_contribution_paise == 175000
    assert summary_effective.contribution_per_shopper_paise == 175000

    # 2. Raw Historical Summary (Audit View)
    summary_raw = await PolicyMemoryService.get_policy_summary(
        db_session,
        merchant_id="merch_recon",
        policy_id="p_treat",
        is_current_only=False
    )
    assert summary_raw.evaluation_view == "RAW_HISTORICAL"
    assert summary_raw.total_opportunities == 2  # Both events audited


@pytest.mark.asyncio
async def test_query_filtering_is_current_only(db_session, seed_recon_merchant):
    """Test deterministic retrieval filtering by is_current_only."""
    opp_id = "exp_recon_01:scen_filter_test:TREATMENT"
    e1 = make_reconciliation_evidence("evi_filt_1", LearningOutcomeType.ORDER_CREATED, 0, 0, opportunity_id=opp_id)
    e2 = make_reconciliation_evidence("evi_filt_2", LearningOutcomeType.PAYMENT_SUCCESS, 100000, 50000, opportunity_id=opp_id)

    mem1 = await PolicyMemoryService.record_observation(db_session, e1)
    mem2 = await PolicyMemoryService.record_observation(db_session, e2)

    # Filter: Current only
    res_curr = await PolicyMemoryService.query_history(
        db_session,
        HistoricalObservationFilter(merchant_id="merch_recon", is_current_only=True)
    )
    curr_ids = [item.memory_id for item in res_curr.items]
    assert mem2.memory_id in curr_ids
    assert mem1.memory_id not in curr_ids

    # Filter: Superseded only
    res_sup = await PolicyMemoryService.query_history(
        db_session,
        HistoricalObservationFilter(merchant_id="merch_recon", is_current_only=False)
    )
    sup_ids = [item.memory_id for item in res_sup.items]
    assert mem1.memory_id in sup_ids
    assert mem2.memory_id not in sup_ids


@pytest.mark.asyncio
async def test_tenant_isolation_in_reconciliation(db_session, seed_recon_merchant):
    """Merchant A cannot supersede or link to Merchant B's opportunity."""
    e_a = make_reconciliation_evidence("evi_iso_a", LearningOutcomeType.ORDER_CREATED, 0, 0, merchant_id="merch_recon")
    e_b = make_reconciliation_evidence("evi_iso_b", LearningOutcomeType.PAYMENT_SUCCESS, 100000, 50000, merchant_id="merch_recon_other")

    mem_a = await PolicyMemoryService.record_observation(db_session, e_a)
    mem_b = await PolicyMemoryService.record_observation(db_session, e_b)

    assert mem_a.is_current is True
    assert mem_b.is_current is True
    # Merchant B's record does not supersede Merchant A's record despite identical opportunity_id string
    assert mem_b.supersedes is None
    assert mem_a.superseded_by is None
