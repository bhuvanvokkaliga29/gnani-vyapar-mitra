"""Transaction State Machine for Order and Payment Lifecycles."""

from enum import Enum
from typing import Set, Dict


class TransactionState(str, Enum):
    """Lifecycle states for a merchant transaction."""
    CREATION_PENDING = "CREATION_PENDING"
    ORDER_CREATED = "ORDER_CREATED"
    UNCERTAIN = "UNCERTAIN"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    FINALIZED = "FINALIZED"


class InvalidStateTransitionError(Exception):
    """Raised when an invalid transaction state transition is attempted."""
    def __init__(self, current_state: TransactionState, target_state: TransactionState, reason: str = ""):
        self.current_state = current_state
        self.target_state = target_state
        message = f"Invalid state transition from {current_state.value} to {target_state.value}."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(message)


class StateMachine:
    """Enforces valid state transitions and terminal state invariants."""

    # Allowed forward transitions
    TRANSITIONS: Dict[TransactionState, Set[TransactionState]] = {
        TransactionState.CREATION_PENDING: {
            TransactionState.ORDER_CREATED,
            TransactionState.UNCERTAIN,
            TransactionState.FAILED
        },
        TransactionState.UNCERTAIN: {
            TransactionState.ORDER_CREATED,
            TransactionState.FAILED
        },
        TransactionState.ORDER_CREATED: {
            TransactionState.PAYMENT_PENDING,
            TransactionState.AUTHORIZED,
            TransactionState.CAPTURED,
            TransactionState.PAID,
            TransactionState.FAILED,
            TransactionState.CANCELLED
        },
        TransactionState.PAYMENT_PENDING: {
            TransactionState.AUTHORIZED,
            TransactionState.CAPTURED,
            TransactionState.PAID,
            TransactionState.FAILED,
            TransactionState.CANCELLED
        },
        TransactionState.AUTHORIZED: {
            TransactionState.CAPTURED,
            TransactionState.PAID,
            TransactionState.FAILED
        },
        TransactionState.CAPTURED: {
            TransactionState.PAID,
            TransactionState.FINALIZED
        },
        TransactionState.PAID: {
            TransactionState.FINALIZED
        },
        TransactionState.FAILED: set(),  # Terminal
        TransactionState.CANCELLED: set(),  # Terminal
        TransactionState.FINALIZED: set()  # Terminal
    }

    TERMINAL_STATES: Set[TransactionState] = {
        TransactionState.PAID,
        TransactionState.FINALIZED,
        TransactionState.FAILED,
        TransactionState.CANCELLED
    }

    @classmethod
    def can_transition(cls, current: TransactionState, target: TransactionState) -> bool:
        """Check if transition from current to target is allowed."""
        if current == target:
            return True
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def validate_transition(cls, current: TransactionState, target: TransactionState) -> None:
        """Validate transition; raise InvalidStateTransitionError if illegal."""
        if not cls.can_transition(current, target):
            # Check for terminal state regression
            if current in cls.TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    current, target, reason="Terminal states cannot be mutated or regressed by stale events."
                )
            raise InvalidStateTransitionError(current, target)
