"""Unit Tests for Phase 9.2 DecisionExecutionBoundaryService.

Contract: execution-boundary/v1
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from domain.models import Merchant, CanonicalDecisionRecord
from services.boundary.schemas import (
    DecisionExecuteRequest,
    ExecutionBoundaryStatus
)
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.errors import (
    DecisionNotFoundError,
    DecisionTenantViolationError
)
from services.commerce_service import MerchantNotFoundError


@pytest.fixture
async def seed_boundary_merchant(db_session):
    """Seed active and suspended test merchants."""
    m_active = Merchant(
        id="merch_bound_active",
        name="Bound Active Merchant",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE"
    )
    m_suspended = Merchant(
        id="merch_bound_suspended",
        name="Bound Suspended Merchant",
        currency="INR",
        status="SUSPENDED",
        business_objective="MAXIMIZE_REVENUE"
    )
    db_session.add_all([m_active, m_suspended])
    await db_session.commit()
    return m_active, m_suspended


@pytest.mark.asyncio
async def test_merchant_not_found_raises(db_session):
    """Execution for non-existent merchant raises MerchantNotFoundError."""
    req = DecisionExecuteRequest(merchant_id="merch_ghost")
    with pytest.raises(MerchantNotFoundError):
        await DecisionExecutionBoundaryService.execute_decision(db_session, "dec_nonexistent", req)


@pytest.mark.asyncio
async def test_inactive_merchant_rejected(db_session, seed_boundary_merchant):
    """Execution for suspended merchant is rejected."""
    _, m_suspended = seed_boundary_merchant
    req = DecisionExecuteRequest(merchant_id=m_suspended.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(db_session, "dec_dummy", req)

    assert resp.boundary_status == ExecutionBoundaryStatus.POLICY_NOT_ACTIVE
    assert resp.execution_authorized is False
    assert any("ACTIVE" in r for r in resp.rejection_reasons)


@pytest.mark.asyncio
async def test_decision_not_found_raises(db_session, seed_boundary_merchant):
    """Execution for non-existent decision raises DecisionNotFoundError."""
    m_active, _ = seed_boundary_merchant
    req = DecisionExecuteRequest(merchant_id=m_active.id)
    with pytest.raises(DecisionNotFoundError):
        await DecisionExecutionBoundaryService.execute_decision(db_session, "dec_missing_999", req)


@pytest.mark.asyncio
async def test_cross_tenant_execution_raises(db_session, seed_boundary_merchant):
    """Merchant B cannot execute Merchant A's decision envelope."""
    m_active, m_suspended = seed_boundary_merchant

    # Seed decision belonging to m_suspended
    dec = CanonicalDecisionRecord(
        id="dec_tenant_01",
        merchant_id=m_suspended.id,
        opportunity_id="opp_tenant_01",
        decision_version="canonical-decision/v1",
        buyer_context_key="ctx_test",
        decision_mode="EXPLOIT",
        decision_reason="TEST",
        selected_policy_id="cand_test",
        selected_strategy_type="NO_OFFER",
        proposed_price_paise=0,
        predicted_contribution_paise=0,
        decision_envelope_json={"dummy": True}
    )
    db_session.add(dec)
    await db_session.commit()

    # m_active attempts to execute m_suspended's decision
    req = DecisionExecuteRequest(merchant_id=m_active.id)
    with pytest.raises(DecisionTenantViolationError):
        await DecisionExecutionBoundaryService.execute_decision(db_session, "dec_tenant_01", req)


@pytest.mark.asyncio
async def test_stale_decision_fails_closed(db_session, seed_boundary_merchant):
    """Decisions older than configured TTL fail closed with DECISION_STALE."""
    m_active, _ = seed_boundary_merchant

    old_created = datetime.now(timezone.utc) - timedelta(seconds=1200)  # 20 mins ago

    dec = CanonicalDecisionRecord(
        id="dec_stale_01",
        merchant_id=m_active.id,
        opportunity_id="opp_stale_01",
        decision_version="canonical-decision/v1",
        buyer_context_key="ctx_test",
        decision_mode="EXPLOIT",
        decision_reason="TEST",
        selected_policy_id="cand_test",
        selected_strategy_type="NO_OFFER",
        proposed_price_paise=0,
        predicted_contribution_paise=0,
        decision_envelope_json={
            "decision_id": "dec_stale_01",
            "merchant_id": m_active.id,
            "opportunity_id": "opp_stale_01",
            "decision_version": "canonical-decision/v1",
            "created_at": old_created.isoformat(),
            "buyer_context_key": "ctx_test",
            "intent_summary": {"category": "travel_backpack", "hard_requirements": [], "preferences": [], "exclusions": []},
            "buyer_offer": {"offer_id": "off_1", "strategy_type": "NO_OFFER", "offered_price_paise": 0, "rationale": "none"},
            "merchant_evaluation": {"selected_policy_id": "cand_test", "strategy_type": "NO_OFFER", "proposed_price_paise": 0, "cogs_paise": 0, "gross_profit_paise": 0, "gross_margin_percent": 0.0, "predicted_contribution_paise": 0, "uncertainty": 0.0, "ucb_score_paise": 0, "composite_ranking_score": 0.0},
            "selected_policy": {"candidate_id": "cand_test", "strategy_type": "NO_OFFER", "product_ids": [], "proposed_price_paise": 0, "rationale": "none"},
            "decision_mode": "EXPLOIT",
            "decision_reason": "TEST",
            "scores": {"predicted_contribution_paise": 0, "uncertainty": 0.0, "ucb_score_paise": 0, "composite_ranking_score": 0.0},
            "safety_audit": {"safety_check_id": "safe_1", "status": "ADMISSIBLE", "is_admissible": True, "rejection_reasons": []},
            "model_metadata": {"model_version": "learning-model/v1", "observation_count": 0, "feature_dimension": 19, "alpha_paise": 10000},
            "trace": {"total_latency_ms": 1.0}
        },
        created_at=old_created
    )
    db_session.add(dec)
    await db_session.commit()

    # Request execution with default 900s TTL (age is 1200s)
    req = DecisionExecuteRequest(merchant_id=m_active.id)
    resp = await DecisionExecutionBoundaryService.execute_decision(
        db_session,
        "dec_stale_01",
        req,
        ttl_seconds=900.0
    )

    assert resp.boundary_status == ExecutionBoundaryStatus.DECISION_STALE
    assert resp.execution_authorized is False
    assert any("DECISION_STALE" in r for r in resp.rejection_reasons)
