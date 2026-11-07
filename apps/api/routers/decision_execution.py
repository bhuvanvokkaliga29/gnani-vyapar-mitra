"""API Router for Phase 9.2 Execution Boundary.

Contract: execution-boundary/v1
Endpoints:
- POST /api/v1/decisions/{decision_id}/execute
- GET  /api/v1/decisions/{decision_id}/execution
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from services.boundary.schemas import DecisionExecuteRequest, DecisionExecuteResponse
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.errors import (
    DecisionNotFoundError,
    DecisionTenantViolationError,
    ExecutionBoundaryError
)
from services.commerce_service import MerchantNotFoundError

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/decisions", tags=["Decision Execution Boundary"])


@router.post(
    "/{decision_id}/execute",
    response_model=DecisionExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Canonical Decision through Runtime Boundary"
)
async def execute_decision(
    decision_id: str,
    request: DecisionExecuteRequest,
    db: AsyncSession = Depends(get_db)
) -> DecisionExecuteResponse:
    """Safely traverse the runtime execution boundary for an existing decision.

    Guarantees:
    1. Active policy / lifecycle verification (Phase 8.8).
    2. Fresh commerce state reload (Phase 2).
    3. Authoritative point-in-time safety re-evaluation (Phase 8.6).
    4. Server-generated single-use authorization token.
    5. Handoff to Phase 5 ExecutionGate into Razorpay Test Mode.
    6. Zero client authority over financial amounts, safety, or tokens.
    """
    try:
        response = await DecisionExecutionBoundaryService.execute_decision(
            db=db,
            decision_id=decision_id,
            request=request
        )
        return response
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (DecisionTenantViolationError, MerchantNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ExecutionBoundaryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("decision_execution_unhandled_error", decision_id=decision_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal execution boundary error"
        )


@router.get(
    "/{decision_id}/execution",
    response_model=DecisionExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Authoritative Boundary Execution Record"
)
async def get_decision_execution(
    decision_id: str,
    merchant_id: str = Query(..., description="Tenant merchant identifier for authorization"),
    db: AsyncSession = Depends(get_db)
) -> DecisionExecuteResponse:
    """Fetch immutable boundary audit record for a given decision."""
    try:
        response = await DecisionExecutionBoundaryService.get_execution(
            db=db,
            decision_id=decision_id,
            merchant_id=merchant_id
        )
        return response
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("get_execution_unhandled_error", decision_id=decision_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve execution record"
        )
