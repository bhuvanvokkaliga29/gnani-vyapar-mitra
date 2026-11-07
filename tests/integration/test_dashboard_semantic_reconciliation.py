"""Tests for Dashboard Semantic Reconciliation, KPI Scopes, and Invariants.

Verifies:
1. Overview KPI formula correctness
2. Test Mode observed aggregation (exact paise sum)
3. Paid transaction aggregation (exact count)
4. Expected contribution aggregation (exact predicted paise sum)
5. Learning insight scope vs total merchant learning observations
6. Active policy evidence scope (baseline cand_base_no_offer has 0 direct promotional margin)
7. Payment failed vs success outcome semantics
8. NO_OFFER execution rejection and trace stopping points
9. Pending execution gate handling
10. Learning center health counters reconciliation
11. Policy page active policy retrieval
12. Trace reconstruction stopping points
13. Authoritative AppliedModelObservationRecord lineage ID retrieval
14. Strict multi-tenant isolation
"""

import pytest
from sqlalchemy import select, func, and_
from domain.models import (
    Base,
    Merchant,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
    AppliedModelObservationRecord,
    MerchantActivePolicy,
)
from services.dashboard.service import (
    DashboardOverviewService,
    DecisionViewService,
    PolicyViewService,
    LearningViewService,
)
from services.observability.trace import TraceReconstructionService, TraceStageStatus
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

LIVE_DB_URL = "sqlite+aiosqlite:///./test.db"
live_engine = create_async_engine(LIVE_DB_URL, connect_args={"check_same_thread": False})
LiveSessionLocal = async_sessionmaker(bind=live_engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture
async def live_db():
    async with live_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with LiveSessionLocal() as session:
        stmt = select(Merchant).where(Merchant.id == "merch_atlas_travel")
        if not (await session.execute(stmt)).scalar_one_or_none():
            from scripts.run_demo_population import seed_demo_merchants, run_population_simulation
            await seed_demo_merchants(session, ["merch_atlas_travel", "merch_alpha"])
            await run_population_simulation(session, "merch_atlas_travel", total_interactions=10)
        yield session

@pytest.mark.asyncio
async def test_overview_kpis_and_aggregates(live_db):
    merchant_id = "merch_atlas_travel"

    # Query authoritative database aggregates directly
    auth_opps = (await live_db.execute(
        select(func.count(func.distinct(CanonicalDecisionRecord.opportunity_id)))
        .where(CanonicalDecisionRecord.merchant_id == merchant_id)
    )).scalar_one()

    auth_decisions = (await live_db.execute(
        select(func.count(CanonicalDecisionRecord.id))
        .where(CanonicalDecisionRecord.merchant_id == merchant_id)
    )).scalar_one()

    auth_execs = (await live_db.execute(
        select(func.count(DecisionExecutionRecord.id))
        .where(
            and_(
                DecisionExecutionRecord.merchant_id == merchant_id,
                DecisionExecutionRecord.boundary_status == "EXECUTION_COMPLETED"
            )
        )
    )).scalar_one()

    auth_paid = (await live_db.execute(
        select(func.count(OutcomeFeedbackRecord.id))
        .where(
            and_(
                OutcomeFeedbackRecord.merchant_id == merchant_id,
                OutcomeFeedbackRecord.transaction_state == "PAID"
            )
        )
    )).scalar_one()

    auth_observed_paise = (await live_db.execute(
        select(func.coalesce(func.sum(OutcomeFeedbackRecord.reward_contribution_paise), 0))
        .where(OutcomeFeedbackRecord.merchant_id == merchant_id)
    )).scalar_one()

    auth_expected_paise = (await live_db.execute(
        select(func.coalesce(func.sum(CanonicalDecisionRecord.predicted_contribution_paise), 0))
        .where(CanonicalDecisionRecord.merchant_id == merchant_id)
    )).scalar_one()

    auth_obs_count = (await live_db.execute(
        select(func.count(AppliedModelObservationRecord.id))
        .where(AppliedModelObservationRecord.merchant_id == merchant_id)
    )).scalar_one()

    # Check merchant overview through service DTO
    overview = await DashboardOverviewService.get_overview(live_db, merchant_id)

    # Invariant: Service DTO values MUST exactly match direct authoritative database queries
    assert overview.ai_buyer_opportunities_count == auth_opps
    assert overview.decision_count == auth_decisions
    assert overview.decision_rate_percent == 100.0
    assert overview.authorized_executions_count == auth_execs
    assert overview.paid_transactions_count == auth_paid
    assert overview.test_mode_observed_contribution_paise == auth_observed_paise
    assert overview.observed_contribution_paise == auth_observed_paise
    assert overview.expected_contribution_paise == auth_expected_paise
    assert overview.total_learning_observations_count == auth_obs_count
    assert overview.total_contexts_count >= 3


@pytest.mark.asyncio
async def test_learning_insight_scope_vs_merchant_learning(live_db):
    merchant_id = "merch_atlas_travel"
    overview = await DashboardOverviewService.get_overview(live_db, merchant_id)

    insight = overview.learning_insight
    assert insight is not None

    # Contextual signal for top candidate
    assert insight.observed_preference_strategy is not None
    assert insight.observed_contribution_paise >= 0
    assert insight.evidence_count >= 1
    assert insight.evidence_strength in ["COLD_START", "EMERGING", "ESTABLISHED"]

    # Total merchant learning is distinct and greater than contextual single-pair observation
    assert overview.total_learning_observations_count >= insight.evidence_count


@pytest.mark.asyncio
async def test_active_policy_evidence_scope(live_db):
    merchant_id = "merch_atlas_travel"
    overview = await DashboardOverviewService.get_overview(live_db, merchant_id)

    # Active policy is cand_base_no_offer
    active_pol = overview.active_policy
    assert active_pol is not None
    assert active_pol.policy_id == "cand_base_no_offer"
    assert active_pol.lifecycle_status == "ACTIVE"

    # Active policy has 0 direct promotional margin because baseline issues NO_OFFER
    assert active_pol.observed_contribution_paise == 0
    assert active_pol.evidence_count == 0


@pytest.mark.asyncio
async def test_decision_detail_authoritative_lineage(live_db):
    merchant_id = "merch_atlas_travel"

    # 1. Successful Purchase: find representative decision with PAYMENT_SUCCESS
    stmt_succ = (
        select(CanonicalDecisionRecord.id)
        .join(DecisionExecutionRecord, DecisionExecutionRecord.decision_id == CanonicalDecisionRecord.id)
        .join(OutcomeFeedbackRecord, OutcomeFeedbackRecord.execution_id == DecisionExecutionRecord.id)
        .where(
            and_(
                CanonicalDecisionRecord.merchant_id == merchant_id,
                OutcomeFeedbackRecord.outcome_status == "PAYMENT_SUCCESS"
            )
        )
        .limit(1)
    )
    dec_success_id = (await live_db.execute(stmt_succ)).scalar()
    assert dec_success_id is not None

    detail_success = await DecisionViewService.get_decision_detail(live_db, dec_success_id, merchant_id)
    assert detail_success.execution_status == "EXECUTION_COMPLETED"
    assert detail_success.outcome_status == "PAYMENT_SUCCESS"
    assert detail_success.order_id is not None
    assert detail_success.payment_id is not None
    assert detail_success.evidence_id is not None
    assert detail_success.memory_id is not None
    assert detail_success.applied_observation_id is not None
    assert detail_success.applied_observation_id.startswith("amo_")
    assert detail_success.reward_contribution_paise > 0

    # 2. Payment Failure: find representative decision with PAYMENT_FAILED
    stmt_fail = (
        select(CanonicalDecisionRecord.id)
        .join(DecisionExecutionRecord, DecisionExecutionRecord.decision_id == CanonicalDecisionRecord.id)
        .join(OutcomeFeedbackRecord, OutcomeFeedbackRecord.execution_id == DecisionExecutionRecord.id)
        .where(
            and_(
                CanonicalDecisionRecord.merchant_id == merchant_id,
                OutcomeFeedbackRecord.outcome_status == "PAYMENT_FAILED"
            )
        )
        .limit(1)
    )
    dec_failed_id = (await live_db.execute(stmt_fail)).scalar()
    assert dec_failed_id is not None

    detail_failed = await DecisionViewService.get_decision_detail(live_db, dec_failed_id, merchant_id)
    assert detail_failed.execution_status == "EXECUTION_COMPLETED"
    assert detail_failed.outcome_status == "PAYMENT_FAILED"
    assert detail_failed.payment_id.startswith("pay_fail_")
    assert detail_failed.reward_contribution_paise == 0
    assert detail_failed.applied_observation_id is not None

    # 3. NO_OFFER / Execution Rejected
    stmt_rej = (
        select(CanonicalDecisionRecord.id)
        .join(DecisionExecutionRecord, DecisionExecutionRecord.decision_id == CanonicalDecisionRecord.id)
        .where(
            and_(
                CanonicalDecisionRecord.merchant_id == merchant_id,
                DecisionExecutionRecord.boundary_status == "EXECUTION_REJECTED"
            )
        )
        .limit(1)
    )
    dec_rejected_id = (await live_db.execute(stmt_rej)).scalar()
    assert dec_rejected_id is not None

    detail_rejected = await DecisionViewService.get_decision_detail(live_db, dec_rejected_id, merchant_id)
    assert detail_rejected.execution_status == "EXECUTION_REJECTED"
    assert detail_rejected.order_id is None
    assert detail_rejected.payment_id is None
    assert detail_rejected.outcome_status is None
    assert detail_rejected.applied_observation_id is None

    # 4. Pending Gate: dec for opp_probe_before
    stmt_pend = select(CanonicalDecisionRecord.id).where(
        and_(
            CanonicalDecisionRecord.merchant_id == merchant_id,
            CanonicalDecisionRecord.opportunity_id == "opp_probe_before"
        )
    ).limit(1)
    dec_pending_id = (await live_db.execute(stmt_pend)).scalar()
    assert dec_pending_id is not None

    detail_pending = await DecisionViewService.get_decision_detail(live_db, dec_pending_id, merchant_id)
    assert detail_pending.execution_status == "PENDING_EXECUTION_GATE"
    assert detail_pending.execution_id is None
    assert detail_pending.order_id is None
    assert detail_pending.outcome_status is None


@pytest.mark.asyncio
async def test_trace_reconstruction_stopping_points(live_db):
    merchant_id = "merch_atlas_travel"

    # Pending gate stops at execution
    trace_pending = await TraceReconstructionService.reconstruct_opportunity(
        db=live_db,
        merchant_id=merchant_id,
        opportunity_id="opp_probe_before"
    )
    assert trace_pending.trace_status == TraceStageStatus.STOPPED_AT_EXECUTION.value

    # NO_OFFER stops at transaction (never creates order/payment)
    stmt_rej_opp = (
        select(CanonicalDecisionRecord.opportunity_id)
        .join(DecisionExecutionRecord, DecisionExecutionRecord.decision_id == CanonicalDecisionRecord.id)
        .where(
            and_(
                CanonicalDecisionRecord.merchant_id == merchant_id,
                DecisionExecutionRecord.boundary_status == "EXECUTION_REJECTED"
            )
        )
        .limit(1)
    )
    opp_no_offer = (await live_db.execute(stmt_rej_opp)).scalar()
    assert opp_no_offer is not None

    trace_no_offer = await TraceReconstructionService.reconstruct_opportunity(
        db=live_db,
        merchant_id=merchant_id,
        opportunity_id=opp_no_offer
    )
    assert trace_no_offer.trace_status == TraceStageStatus.STOPPED_AT_TRANSACTION.value

    # Successful purchase reaches complete lineage
    stmt_succ_opp = (
        select(OutcomeFeedbackRecord.opportunity_id)
        .where(
            and_(
                OutcomeFeedbackRecord.merchant_id == merchant_id,
                OutcomeFeedbackRecord.outcome_status == "PAYMENT_SUCCESS"
            )
        )
        .limit(1)
    )
    opp_success = (await live_db.execute(stmt_succ_opp)).scalar()
    assert opp_success is not None

    trace_success = await TraceReconstructionService.reconstruct_opportunity(
        db=live_db,
        merchant_id=merchant_id,
        opportunity_id=opp_success
    )
    assert "9.1_DECISION" in trace_success.stages_present
    assert "9.2_EXECUTION" in trace_success.stages_present
    assert "PHASE_5_ORDER" in trace_success.stages_present
    assert "PHASE_5_PAYMENT" in trace_success.stages_present
    assert "9.3_OUTCOME" in trace_success.stages_present
    assert "8.1_EVIDENCE" in trace_success.stages_present
    assert "8.3_MEMORY" in trace_success.stages_present


@pytest.mark.asyncio
async def test_learning_center_health_counters(live_db):
    merchant_id = "merch_atlas_travel"
    learning = await LearningViewService.get_learning_center(live_db, merchant_id)

    auth_ev_cnt = (await live_db.execute(
        select(func.count(LearningEvidenceRecord.id)).where(LearningEvidenceRecord.merchant_id == merchant_id)
    )).scalar_one()
    auth_mem_cnt = (await live_db.execute(
        select(func.count(PolicyMemoryRecord.id)).where(PolicyMemoryRecord.merchant_id == merchant_id)
    )).scalar_one()
    auth_updates_cnt = (await live_db.execute(
        select(func.count(AppliedModelObservationRecord.id)).where(AppliedModelObservationRecord.merchant_id == merchant_id)
    )).scalar_one()

    assert learning.health.valid_evidence_count == auth_ev_cnt
    assert learning.health.rejected_evidence_count == 0
    assert learning.health.memory_observations_count == auth_mem_cnt
    assert learning.health.model_updates_count == auth_updates_cnt
    assert learning.model_metadata.observation_count == auth_updates_cnt
    assert learning.model_metadata.learning_status == "OPTIMIZING"


@pytest.mark.asyncio
async def test_policy_page_reconciliation(live_db):
    merchant_id = "merch_atlas_travel"
    policy_data = await PolicyViewService.get_policies(live_db, merchant_id)

    assert policy_data.active_policy is not None
    assert policy_data.active_policy.policy_id == "cand_base_no_offer"
    assert policy_data.active_policy.lifecycle_status == "ACTIVE"
    assert policy_data.active_policy.observed_contribution_paise == 0
    assert policy_data.active_policy.evidence_count == 0


@pytest.mark.asyncio
async def test_tenant_isolation_semantics(live_db):
    # Atlas Travel Gear
    auth_atlas_opps = (await live_db.execute(
        select(func.count(func.distinct(CanonicalDecisionRecord.opportunity_id)))
        .where(CanonicalDecisionRecord.merchant_id == "merch_atlas_travel")
    )).scalar_one()
    auth_atlas_paid = (await live_db.execute(
        select(func.count(OutcomeFeedbackRecord.id))
        .where(
            and_(
                OutcomeFeedbackRecord.merchant_id == "merch_atlas_travel",
                OutcomeFeedbackRecord.transaction_state == "PAID"
            )
        )
    )).scalar_one()

    atlas_overview = await DashboardOverviewService.get_overview(live_db, "merch_atlas_travel")
    assert atlas_overview.ai_buyer_opportunities_count == auth_atlas_opps
    assert atlas_overview.paid_transactions_count == auth_atlas_paid
    assert atlas_overview.ai_buyer_opportunities_count > 0

    # Alpha Outfitters
    auth_alpha_opps = (await live_db.execute(
        select(func.count(func.distinct(CanonicalDecisionRecord.opportunity_id)))
        .where(CanonicalDecisionRecord.merchant_id == "merch_alpha")
    )).scalar_one()
    auth_alpha_paid = (await live_db.execute(
        select(func.count(OutcomeFeedbackRecord.id))
        .where(
            and_(
                OutcomeFeedbackRecord.merchant_id == "merch_alpha",
                OutcomeFeedbackRecord.transaction_state == "PAID"
            )
        )
    )).scalar_one()

    alpha_overview = await DashboardOverviewService.get_overview(live_db, "merch_alpha")
    assert alpha_overview.ai_buyer_opportunities_count == auth_alpha_opps
    assert alpha_overview.paid_transactions_count == auth_alpha_paid

    # Cross-tenant decision lookup rejected
    stmt_atlas = select(CanonicalDecisionRecord.id).where(
        CanonicalDecisionRecord.merchant_id == "merch_atlas_travel"
    ).limit(1)
    dec_atlas_id = (await live_db.execute(stmt_atlas)).scalar()
    assert dec_atlas_id is not None

    with pytest.raises(Exception):
        await DecisionViewService.get_decision_detail(live_db, dec_atlas_id, "merch_alpha")

