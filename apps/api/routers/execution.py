"""API Endpoints for Phase 5 Deterministic Commercial Policy Execution."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from domain.models import ExecutionRecord
from services.execution.schemas import (
    PolicyExecuteRequest,
    PolicyExecuteResponse,
    ExecutionAuthorization,
    ExecutionState
)
from services.execution.gate import ExecutionGate

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/policy", tags=["Policy Execution Gate"])


def get_execution_gate() -> ExecutionGate:
    return ExecutionGate()


@router.post("/execute", response_model=PolicyExecuteResponse, status_code=status.HTTP_200_OK)
async def execute_policy(
    request: PolicyExecuteRequest,
    db: AsyncSession = Depends(get_db),
    gate: ExecutionGate = Depends(get_execution_gate)
):
    """Authoritative execution gate for commercial policy proposals.

    SECURITY INVARIANT:
    All prices, discounts, margins, and currency are recomputed server-side from fresh
    merchant database state. Client-supplied amounts are strictly ignored and forbidden.
    """
    try:
        response = await gate.execute_policy(db=db, request=request)
        return response
    except Exception as exc:
        logger.error("policy_execution_unhandled_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal execution gate error during policy revalidation"
        )


@router.get("/executions/{execution_id}", response_model=PolicyExecuteResponse, status_code=status.HTTP_200_OK)
async def get_execution_record(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve immutable audit details for a commercial policy execution."""
    stmt = select(ExecutionRecord).where(ExecutionRecord.id == execution_id)
    record = (await db.execute(stmt)).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution record '{execution_id}' not found."
        )

    auth_dto = ExecutionAuthorization(
        authorization_id=f"auth_{record.id[:12]}",
        proposal_id=record.proposal_id,
        merchant_id=record.merchant_id,
        candidate_id=record.candidate_id,
        authorized_amount_paise=record.authorized_amount_paise,
        currency=record.currency,
        status=record.status,
        rejection_reasons=record.rejection_reasons or [],
        recalculated_economics=record.recalculated_economics,
        receipt=record.receipt,
        idempotency_key=record.idempotency_key,
        authorized_at=record.created_at
    )

    state = ExecutionState(record.status) if record.status in ExecutionState._value2member_map_ else ExecutionState.ORDER_CREATED

    return PolicyExecuteResponse(
        execution_id=record.id,
        status=state,
        authorization=auth_dto,
        order_id=record.order_id,
        razorpay_order_id=record.razorpay_order_id,
        authorized_amount_paise=record.authorized_amount_paise,
        currency=record.currency,
        is_duplicate=False,
        latency_ms=0.0
    )
