"""Comprehensive Semantic & Cross-Layer Verification for AI Decision Detail Drawer.

Razorpay AI Track 01 - Merchant AI Control Center.
Verifies authoritative reconciliation across DB -> Service -> DTO -> UI.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_

from services.dashboard.service import DecisionViewService, PolicyViewService
from domain.models import (
    Base,
    Merchant,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
    LearningEvidenceRecord,
    PolicyMemoryRecord,
    AppliedModelObservationRecord,
)
from services.commerce_service import MerchantNotFoundError


@pytest_asyncio.fixture
async def db_session():
    """Async database session connected to active test.db, hermetically initialized."""
    engine = create_async_engine("sqlite+aiosqlite:///./test.db", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Check if seeded; if not, seed demo data
        stmt = select(Merchant).where(Merchant.id == "merch_atlas_travel")
        if not (await session.execute(stmt)).scalar_one_or_none():
            from scripts.run_demo_population import seed_demo_merchants, run_population_simulation
            await seed_demo_merchants(session, ["merch_atlas_travel", "merch_alpha"])
            await run_population_simulation(session, "merch_atlas_travel", total_interactions=10)
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_decision_detail_field_reconciliation_dec_fdd(db_session: AsyncSession):
    """Test full 11-stage lineage and field reconciliation for representative completed decision."""
    merchant_id = "merch_atlas_travel"
    
    # Dynamically find a decision that completed execution with payment failure (Path B)
    stmt = (
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
    dec_id = (await db_session.execute(stmt)).scalar()
    assert dec_id is not None, "Representative PAYMENT_FAILED decision must exist in DB"

    detail = await DecisionViewService.get_decision_detail(db_session, dec_id, merchant_id)

    # 1. 11-stage lineage integrity
    assert detail.decision_id == dec_id
    assert detail.request_id is not None
    assert detail.opportunity_id is not None
    assert detail.authorization_id is not None
    assert detail.execution_id is not None
    assert detail.order_id is not None
    assert detail.payment_id is not None
    assert detail.outcome_id is not None
    assert detail.evidence_id is not None
    assert detail.memory_id is not None
    assert detail.applied_observation_id is not None

    # Verify amo_id is genuine database ID, NOT synthetic slice
    amo_stmt = select(AppliedModelObservationRecord).where(
        AppliedModelObservationRecord.id == detail.applied_observation_id
    )
    amo_row = (await db_session.execute(amo_stmt)).scalar_one_or_none()
    assert amo_row is not None
    assert amo_row.evidence_id == detail.evidence_id
    assert amo_row.merchant_id == merchant_id

    # 2. Strict Buyer View vs Merchant Private Economics Separation
    buyer_view = detail.buyer_offer
    assert buyer_view.offer_price_paise > 0
    assert buyer_view.strategy_type is not None
    # Buyer view does NOT have financial margin fields
    assert not hasattr(buyer_view, "cogs_paise")
    assert not hasattr(buyer_view, "gross_margin_percent")
    assert not hasattr(buyer_view, "predicted_contribution_paise")

    # Merchant Private Evaluation
    merchant_eval = detail.merchant_evaluation
    assert merchant_eval.cogs_paise >= 0
    assert merchant_eval.gross_profit_paise is not None
    assert merchant_eval.gross_margin_percent is not None
    assert merchant_eval.predicted_contribution_paise is not None
    assert merchant_eval.decision_mode in ["EXPLORE", "EXPLOIT"]

    # Gross profit arithmetic: offer_price - cogs = gross_profit
    assert buyer_view.offer_price_paise - merchant_eval.cogs_paise == merchant_eval.gross_profit_paise

    # 3. Candidate & Score Semantics
    assert len(detail.candidates) >= 1
    selected_cands = [c for c in detail.candidates if c.is_selected]
    assert len(selected_cands) == 1
    cand = selected_cands[0]
    assert cand.candidate_id is not None
    assert cand.proposed_price_paise == buyer_view.offer_price_paise
    assert cand.is_selected is True

    # 4. Execution vs Payment Outcome Distinction
    assert detail.execution_status == "EXECUTION_COMPLETED"
    assert detail.outcome_status == "PAYMENT_FAILED"
    assert detail.learning_eligible is True
    assert detail.reward_contribution_paise == 0


@pytest.mark.asyncio
async def test_active_policy_remains_distinct(db_session: AsyncSession):
    """Test that candidate selection in explore/exploit never mutates active governed baseline policy."""
    merchant_id = "merch_atlas_travel"
    policies = await PolicyViewService.get_policies(db_session, merchant_id)

    # Active governed policy is cand_base_no_offer
    assert policies.active_policy is not None
    assert policies.active_policy.policy_id == "cand_base_no_offer"

    # Find a decision that explored/exploited a candidate
    stmt = (
        select(CanonicalDecisionRecord.id)
        .where(
            and_(
                CanonicalDecisionRecord.merchant_id == merchant_id,
                CanonicalDecisionRecord.selected_policy_id != "cand_base_no_offer"
            )
        )
        .limit(1)
    )
    dec_id = (await db_session.execute(stmt)).scalar()
    assert dec_id is not None

    dec = await DecisionViewService.get_decision_detail(db_session, dec_id, merchant_id)
    selected_cand = next((c for c in dec.candidates if c.is_selected), dec.candidates[0])
    assert selected_cand.candidate_id != policies.active_policy.policy_id


@pytest.mark.asyncio
async def test_decision_lifecycle_stopping_points(db_session: AsyncSession):
    """Test stopping points for rejected execution and pending gate."""
    merchant_id = "merch_atlas_travel"

    # 1. NO_OFFER / Execution Rejected
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
    dec_rejected_id = (await db_session.execute(stmt_rej)).scalar()
    assert dec_rejected_id is not None, "Representative EXECUTION_REJECTED decision must exist"

    dec_rejected = await DecisionViewService.get_decision_detail(db_session, dec_rejected_id, merchant_id)
    assert dec_rejected.execution_status == "EXECUTION_REJECTED"
    assert dec_rejected.request_id is not None
    assert dec_rejected.opportunity_id is not None
    assert dec_rejected.decision_id == dec_rejected_id
    assert dec_rejected.authorization_id is not None
    assert dec_rejected.execution_id is not None
    # Downstream stages MUST be None ("Not reached")
    assert dec_rejected.order_id is None
    assert dec_rejected.payment_id is None
    assert dec_rejected.outcome_id is None
    assert dec_rejected.evidence_id is None
    assert dec_rejected.memory_id is None
    assert dec_rejected.applied_observation_id is None

    # 2. Pending Execution Gate
    stmt_pending = select(CanonicalDecisionRecord.id).where(
        and_(
            CanonicalDecisionRecord.merchant_id == merchant_id,
            CanonicalDecisionRecord.opportunity_id == "opp_probe_before"
        )
    ).limit(1)
    dec_pending_id = (await db_session.execute(stmt_pending)).scalar()
    assert dec_pending_id is not None, "opp_probe_before decision must exist"

    dec_pending = await DecisionViewService.get_decision_detail(db_session, dec_pending_id, merchant_id)
    assert dec_pending.execution_status == "PENDING_EXECUTION_GATE"
    assert dec_pending.request_id is not None
    assert dec_pending.opportunity_id is not None
    assert dec_pending.decision_id == dec_pending_id
    assert dec_pending.authorization_id is None
    assert dec_pending.execution_id is None
    assert dec_pending.order_id is None
    assert dec_pending.payment_id is None
    assert dec_pending.outcome_id is None
    assert dec_pending.evidence_id is None
    assert dec_pending.memory_id is None
    assert dec_pending.applied_observation_id is None


@pytest.mark.asyncio
async def test_decision_tenant_isolation(db_session: AsyncSession):
    """Test cross-tenant decision retrieval is rejected with 404/MerchantNotFoundError."""
    stmt = select(CanonicalDecisionRecord.id).where(
        CanonicalDecisionRecord.merchant_id == "merch_atlas_travel"
    ).limit(1)
    dec_id = (await db_session.execute(stmt)).scalar()
    assert dec_id is not None

    # Attempt to access Atlas Travel Gear decision using Alpha Outfitters tenant
    with pytest.raises(MerchantNotFoundError):
        await DecisionViewService.get_decision_detail(
            db_session,
            dec_id,
            "merch_alpha_outfitters"
        )
