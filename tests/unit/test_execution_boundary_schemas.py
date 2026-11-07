"""Unit Tests for Phase 9.2 Execution Boundary Schemas.

Contract: execution-boundary/v1
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from services.boundary.schemas import (
    EXECUTION_BOUNDARY_SCHEMA_VERSION,
    ExecutionBoundaryStatus,
    DecisionExecuteRequest,
    DecisionExecuteResponse,
)


def test_decision_execute_request_validation():
    """Valid execution request passes validation."""
    req = DecisionExecuteRequest(merchant_id="merch_valid_01")
    assert req.merchant_id == "merch_valid_01"
    assert req.idempotency_key is None


def test_decision_execute_request_forbids_client_financial_authority():
    """Clients CANNOT pass amounts, authorization tokens, or safety flags."""
    with pytest.raises(ValidationError):
        DecisionExecuteRequest(
            merchant_id="merch_valid_01",
            authorized_amount_paise=100  # FORBIDDEN!
        )

    with pytest.raises(ValidationError):
        DecisionExecuteRequest(
            merchant_id="merch_valid_01",
            authorization_id="fake_auth_token"  # FORBIDDEN!
        )

    with pytest.raises(ValidationError):
        DecisionExecuteRequest(
            merchant_id="merch_valid_01",
            safety_status="ADMISSIBLE"  # FORBIDDEN!
        )


def test_decision_execute_response_schema_integrity():
    """Valid DecisionExecuteResponse conforms to execution-boundary/v1."""
    now = datetime.now(timezone.utc)
    resp = DecisionExecuteResponse(
        execution_id="dexec_123456",
        decision_id="dec_789012",
        merchant_id="merch_valid_01",
        opportunity_id="opp_abc",
        boundary_status=ExecutionBoundaryStatus.EXECUTION_COMPLETED,
        execution_authorized=True,
        authorization_id="eauth_xyz",
        safety_check_id="safe_123",
        phase5_execution_id="exec_p5_456",
        order_id="order_internal_789",
        razorpay_order_id="order_rzp_test_999",
        authorized_amount_paise=427500,
        currency="INR",
        is_duplicate=False,
        executed_at=now
    )

    assert resp.boundary_version == EXECUTION_BOUNDARY_SCHEMA_VERSION
    assert resp.execution_authorized is True
    assert resp.authorized_amount_paise == 427500

    # Information hygiene: Ensure no COGS, margins, or private bandit weights
    dumped = resp.model_dump()
    assert "cogs_paise" not in dumped
    assert "gross_margin_percent" not in dumped
    assert "gross_profit_paise" not in dumped
    assert "ucb_score" not in dumped


def test_decision_execute_response_forbids_extra_fields():
    """Response strictly rejects unexpected fields."""
    with pytest.raises(ValidationError):
        DecisionExecuteResponse(
            execution_id="dexec_123456",
            decision_id="dec_789012",
            merchant_id="merch_valid_01",
            opportunity_id="opp_abc",
            boundary_status=ExecutionBoundaryStatus.EXECUTION_COMPLETED,
            execution_authorized=True,
            extra_field="disallowed"
        )
