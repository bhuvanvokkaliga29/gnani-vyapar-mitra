"""Unit tests for transaction state machine transitions and terminal invariants."""

import pytest
from apps.api.core.state_machine import (
    TransactionState,
    StateMachine,
    InvalidStateTransitionError
)


def test_valid_forward_transitions():
    """Verify standard happy-path progression through the lifecycle."""
    StateMachine.validate_transition(TransactionState.CREATION_PENDING, TransactionState.ORDER_CREATED)
    StateMachine.validate_transition(TransactionState.ORDER_CREATED, TransactionState.PAID)
    StateMachine.validate_transition(TransactionState.PAID, TransactionState.FINALIZED)


def test_uncertain_state_transitions():
    """Verify recovery transitions from UNCERTAIN state."""
    StateMachine.validate_transition(TransactionState.CREATION_PENDING, TransactionState.UNCERTAIN)
    StateMachine.validate_transition(TransactionState.UNCERTAIN, TransactionState.ORDER_CREATED)
    StateMachine.validate_transition(TransactionState.UNCERTAIN, TransactionState.FAILED)


def test_illegal_jump_rejected():
    """Skipping necessary intermediate states must be rejected."""
    with pytest.raises(InvalidStateTransitionError):
        StateMachine.validate_transition(TransactionState.CREATION_PENDING, TransactionState.FINALIZED)


def test_terminal_state_cannot_regress():
    """Terminal states (PAID, FINALIZED, FAILED) must never regress to previous states."""
    with pytest.raises(InvalidStateTransitionError, match="Terminal states cannot be mutated"):
        StateMachine.validate_transition(TransactionState.PAID, TransactionState.ORDER_CREATED)

    with pytest.raises(InvalidStateTransitionError, match="Terminal states cannot be mutated"):
        StateMachine.validate_transition(TransactionState.PAID, TransactionState.CREATION_PENDING)

    with pytest.raises(InvalidStateTransitionError, match="Terminal states cannot be mutated"):
        StateMachine.validate_transition(TransactionState.FAILED, TransactionState.ORDER_CREATED)
