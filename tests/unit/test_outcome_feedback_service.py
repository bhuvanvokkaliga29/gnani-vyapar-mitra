"""Unit Tests for Phase 9.3 OutcomeFeedbackService.

Contract: outcome-feedback/v1
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from domain.models import (
    Merchant,
    Order,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    OutcomeFeedbackRecord,
)
from apps.api.core.state_machine import TransactionState
from services.outcome.schemas import (
    OutcomeStatus,
    ProcessingState,
    OutcomeProcessRequest,
)
from services.outcome.service import OutcomeFeedbackService
from services.outcome.errors import (
    ExecutionRecordNotFoundError,
    OutcomeTenantViolationError,
)
from services.commerce_service import MerchantNotFoundError


def test_state_mapping_and_eligibility_rules():
    """Verify deterministic mapping of Phase 5 TransactionStates to outcome-feedback/v1."""
    # 1. Successful payment -> Terminal, Learning Eligible
    status, is_term, is_elig, reasons = OutcomeFeedbackService._map_state_and_eligibility(
        TransactionState.PAID, "EXECUTION_COMPLETED"
    )
    assert status == OutcomeStatus.PAYMENT_SUCCESS
    assert is_term is True
    assert is_elig is True
    assert len(reasons) == 0

    # 2. Failed payment -> Terminal, Learning Eligible (non-purchase observation)
    status, is_term, is_elig, reasons = OutcomeFeedbackService._map_state_and_eligibility(
        TransactionState.FAILED, "EXECUTION_COMPLETED"
    )
    assert status == OutcomeStatus.PAYMENT_FAILED
    assert is_term is True
    assert is_elig is True

    # 3. Cancelled payment -> Terminal, Learning Eligible (non-purchase observation)
    status, is_term, is_elig, reasons = OutcomeFeedbackService._map_state_and_eligibility(
        TransactionState.CANCELLED, "EXECUTION_COMPLETED"
    )
    assert status == OutcomeStatus.PAYMENT_CANCELLED
    assert is_term is True
    assert is_elig is True

    # 4. ORDER_CREATED -> Non-terminal, NOT learning eligible (firewall blocks!)
    status, is_term, is_elig, reasons = OutcomeFeedbackService._map_state_and_eligibility(
        TransactionState.ORDER_CREATED, "EXECUTION_COMPLETED"
    )
    assert status == OutcomeStatus.ORDER_CREATED
    assert is_term is False
    assert is_elig is False
    assert any("non-terminal" in r for r in reasons)

    # 5. UNCERTAIN -> Non-terminal, UNRESOLVED, NOT learning eligible
    status, is_term, is_elig, reasons = OutcomeFeedbackService._map_state_and_eligibility(
        TransactionState.UNCERTAIN, "EXECUTION_COMPLETED"
    )
    assert status == OutcomeStatus.UNRESOLVED
    assert is_term is False
    assert is_elig is False

    # 6. Boundary failure (e.g. SAFETY_REJECTED) -> Terminal, Learning Eligible (guardrail failure)
    status, is_term, is_elig, reasons = OutcomeFeedbackService._map_state_and_eligibility(
        TransactionState.FAILED, "SAFETY_REJECTED"
    )
    assert status == OutcomeStatus.EXECUTION_FAILED
    assert is_term is True
    assert is_elig is True


@pytest.fixture
async def seed_unit_merchants(db_session):
    """Seed active merchants for unit testing."""
    mA = Merchant(
        id="merch_unit_out_a",
        name="Unit Merchant A",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE"
    )
    mB = Merchant(
        id="merch_unit_out_b",
        name="Unit Merchant B",
        currency="INR",
        status="ACTIVE",
        business_objective="MAXIMIZE_REVENUE"
    )
    db_session.add_all([mA, mB])
    await db_session.commit()
    return mA, mB


@pytest.mark.asyncio
async def test_merchant_not_found_raises(db_session):
    """Unknown merchant raises MerchantNotFoundError."""
    req = OutcomeProcessRequest(merchant_id="merch_ghost", execution_id="dexec_dummy")
    with pytest.raises(MerchantNotFoundError):
        await OutcomeFeedbackService.process_outcome(db_session, req)


@pytest.mark.asyncio
async def test_execution_not_found_raises(db_session, seed_unit_merchants):
    """Non-existent execution raises ExecutionRecordNotFoundError."""
    mA, _ = seed_unit_merchants
    req = OutcomeProcessRequest(merchant_id=mA.id, execution_id="dexec_nonexistent_999")
    with pytest.raises(ExecutionRecordNotFoundError):
        await OutcomeFeedbackService.process_outcome(db_session, req)


@pytest.mark.asyncio
async def test_cross_tenant_execution_raises(db_session, seed_unit_merchants):
    """Merchant B cannot process Merchant A's execution outcome."""
    mA, mB = seed_unit_merchants

    dexec = DecisionExecutionRecord(
        id="dexec_tenant_test_01",
        merchant_id=mA.id,
        decision_id="dec_dummy_01",
        opportunity_id="opp_dummy_01",
        authorization_id="eauth_dummy_01",
        policy_id="cand_dummy",
        policy_version="merchant-policy/v1",
        state_fingerprint="fp_dummy",
        boundary_status="EXECUTION_COMPLETED",
        idempotency_key="idem_dexec_test_01"
    )
    db_session.add(dexec)
    await db_session.commit()

    # Merchant B attempts to process Merchant A's execution
    req = OutcomeProcessRequest(merchant_id=mB.id, execution_id=dexec.id)
    with pytest.raises(OutcomeTenantViolationError):
        await OutcomeFeedbackService.process_outcome(db_session, req)


@pytest.mark.asyncio
async def test_order_created_non_terminal_outcome(db_session, seed_unit_merchants):
    """When order is created but not paid, outcome is recorded as non-terminal and NOT eligible for learning."""
    mA, _ = seed_unit_merchants

    # 1. Seed Order in ORDER_CREATED state
    order = Order(
        id="ord_test_pending_01",
        decision_id="dec_unit_pending_01",
        razorpay_order_id="order_rzp_pending_01",
        amount_paise=450000,
        currency="INR",
        receipt="rcpt_test_01",
        status=TransactionState.ORDER_CREATED.value
    )
    db_session.add(order)

    # 2. Seed DecisionExecutionRecord
    dexec = DecisionExecutionRecord(
        id="dexec_test_pending_01",
        merchant_id=mA.id,
        decision_id=order.decision_id,
        opportunity_id="opp_unit_pending_01",
        authorization_id="eauth_unit_pending_01",
        policy_id="cand_test",
        policy_version="merchant-policy/v1",
        state_fingerprint="fp_test",
        boundary_status="EXECUTION_COMPLETED",
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        authorized_amount_paise=450000,
        idempotency_key="idem_dexec_pending_01"
    )
    db_session.add(dexec)
    await db_session.commit()

    # 3. Process outcome
    req = OutcomeProcessRequest(merchant_id=mA.id, execution_id=dexec.id)
    resp = await OutcomeFeedbackService.process_outcome(db_session, req)

    # Invariants
    assert resp.outcome_status == OutcomeStatus.ORDER_CREATED
    assert resp.is_terminal is False
    assert resp.learning_eligible is False
    assert resp.evidence_id is None
    assert resp.memory_id is None
    assert any("non-terminal" in r for r in resp.rejection_reasons)
