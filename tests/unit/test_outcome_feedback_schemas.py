"""Unit Tests for Phase 9.3 Outcome Feedback Schemas.

Contract: outcome-feedback/v1
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from services.outcome.schemas import (
    OUTCOME_FEEDBACK_SCHEMA_VERSION,
    OutcomeStatus,
    ProcessingState,
    OutcomeProcessRequest,
    OutcomeProcessResponse,
)


def test_outcome_process_request_validation():
    """Valid request passes validation."""
    req = OutcomeProcessRequest(
        merchant_id="merch_valid_01",
        execution_id="dexec_123456"
    )
    assert req.merchant_id == "merch_valid_01"
    assert req.execution_id == "dexec_123456"
    assert req.idempotency_key is None


def test_outcome_process_request_forbids_client_authority():
    """Clients CANNOT pass financial amounts, payment success flags, or rewards."""
    with pytest.raises(ValidationError):
        OutcomeProcessRequest(
            merchant_id="merch_valid_01",
            execution_id="dexec_123456",
            payment_success=True  # FORBIDDEN!
        )

    with pytest.raises(ValidationError):
        OutcomeProcessRequest(
            merchant_id="merch_valid_01",
            execution_id="dexec_123456",
            reward_paise=50000  # FORBIDDEN!
        )

    with pytest.raises(ValidationError):
        OutcomeProcessRequest(
            merchant_id="merch_valid_01",
            execution_id="dexec_123456",
            realized_revenue_paise=450000  # FORBIDDEN!
        )


def test_outcome_process_response_schema_integrity():
    """Valid OutcomeProcessResponse conforms to outcome-feedback/v1."""
    now = datetime.now(timezone.utc)
    resp = OutcomeProcessResponse(
        outcome_id="out_123456",
        merchant_id="merch_valid_01",
        opportunity_id="opp_abc",
        decision_id="dec_789012",
        execution_id="dexec_456789",
        order_id="ord_internal_111",
        razorpay_order_id="order_rzp_999",
        razorpay_payment_id="pay_rzp_888",
        transaction_state="PAID",
        outcome_status=OutcomeStatus.PAYMENT_SUCCESS,
        processing_state=ProcessingState.COMPLETED,
        is_terminal=True,
        learning_eligible=True,
        evidence_id="evi_123",
        memory_id="mem_456",
        realized_revenue_paise=450000,
        reward_contribution_paise=200000,
        is_duplicate=False,
        processed_at=now
    )

    assert resp.feedback_version == OUTCOME_FEEDBACK_SCHEMA_VERSION
    assert resp.outcome_status == OutcomeStatus.PAYMENT_SUCCESS
    assert resp.is_terminal is True
    assert resp.learning_eligible is True

    # Information hygiene: Ensure no COGS or gross margins are leaked in public response
    dumped = resp.model_dump()
    assert "cogs_paise" not in dumped
    assert "gross_margin_percent" not in dumped
    assert "model_weights" not in dumped


def test_outcome_process_response_forbids_extra_fields():
    """Response strictly rejects unexpected fields."""
    with pytest.raises(ValidationError):
        OutcomeProcessResponse(
            outcome_id="out_123456",
            merchant_id="merch_valid_01",
            opportunity_id="opp_abc",
            decision_id="dec_789012",
            execution_id="dexec_456789",
            transaction_state="PAID",
            outcome_status=OutcomeStatus.PAYMENT_SUCCESS,
            processing_state=ProcessingState.COMPLETED,
            is_terminal=True,
            learning_eligible=True,
            extra_field="disallowed"
        )
