"""Unit tests for Phase 5 Execution Gate schemas."""

import pytest
from pydantic import ValidationError
from services.execution.schemas import (
    ExecutionState,
    ExecutionRejectionReason,
    ExecutionAuthorization,
    PolicyExecuteRequest,
    PolicyExecuteResponse
)
from services.policy.schemas import PolicyProposal, ProposalStatus


def test_execution_state_enums():
    """Verify standard execution lifecycle states."""
    assert ExecutionState.PROPOSAL_RECEIVED.value == "PROPOSAL_RECEIVED"
    assert ExecutionState.EXECUTION_AUTHORIZED.value == "EXECUTION_AUTHORIZED"
    assert ExecutionState.EXECUTION_REJECTED.value == "EXECUTION_REJECTED"
    assert ExecutionState.ORDER_CREATED.value == "ORDER_CREATED"
    assert ExecutionState.PAID.value == "PAID"


def test_execution_rejection_reason_enums():
    """Verify machine-readable rejection codes."""
    assert ExecutionRejectionReason.OUT_OF_STOCK.value == "OUT_OF_STOCK"
    assert ExecutionRejectionReason.MARGIN_TOO_LOW.value == "MARGIN_TOO_LOW"
    assert ExecutionRejectionReason.NO_EXECUTABLE_OFFER.value == "NO_EXECUTABLE_OFFER"
    assert ExecutionRejectionReason.CONCURRENCY_CONFLICT.value == "CONCURRENCY_CONFLICT"


def test_policy_execute_request_forbids_client_amounts():
    """Security Invariant: Callers cannot smuggle price, discount, or margin amounts."""
    with pytest.raises(ValidationError):
        PolicyExecuteRequest(
            merchant_id="merch_01",
            proposal_id="prop_01",
            amount_paise=100  # Extra forbidden!
        )


def test_execution_authorization_schema():
    """Verify valid authorization object construction."""
    auth = ExecutionAuthorization(
        authorization_id="auth_123456789012",
        proposal_id="prop_123456",
        merchant_id="merch_atlas",
        candidate_id="cand_01",
        authorized_amount_paise=450000,
        currency="INR",
        status="EXECUTION_AUTHORIZED",
        receipt="rcpt_123456",
        idempotency_key="idem_01"
    )
    assert auth.authorized_amount_paise == 450000
    assert auth.currency == "INR"
    assert auth.status == "EXECUTION_AUTHORIZED"
