"""FastAPI Router for Phase 9.3 Outcome, Feedback & Recovery Loop.

Contract: outcome-feedback/v1
Endpoints:
- POST /api/v1/outcomes/process
- GET  /api/v1/outcomes/{outcome_id}
- GET  /api/v1/executions/{execution_id}/outcome
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from services.outcome.schemas import (
    OutcomeProcessRequest,
    OutcomeProcessResponse,
)
from services.outcome.service import OutcomeFeedbackService
from services.outcome.errors import (
    ExecutionRecordNotFoundError,
    OutcomeTenantViolationError,
    OutcomeFeedbackError,
)
from services.commerce_service import MerchantNotFoundError

logger = structlog.get_logger()

router = APIRouter(tags=["Outcome Feedback & Recovery"])


@router.post(
    "/api/v1/outcomes/process",
    response_model=OutcomeProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Execution Outcome & Advance Closed-Loop Learning"
)
async def process_outcome(
    request: OutcomeProcessRequest,
    db: AsyncSession = Depends(get_db)
) -> OutcomeProcessResponse:
    """Process execution outcome, verify authoritative transaction truth, and advance learning.

    Guarantees:
    1. Resolves authoritative Phase 5 transaction state.
    2. Enforces learning eligibility firewall (blocks ORDER_CREATED, UNRESOLVED).
    3. Ingests Phase 8.1 evidence & Phase 8.2 reward.
    4. Records immutable Phase 8.3 memory observation.
    5. Updates Phase 8.4 Contextual LinUCB model.
    6. At-least-once delivery with idempotent exactly-once learning effect.
    """
    try:
        response = await OutcomeFeedbackService.process_outcome(
            db=db,
            request=request
        )
        return response
    except ExecutionRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (OutcomeTenantViolationError, MerchantNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except OutcomeFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("outcome_process_unhandled_error", execution_id=request.execution_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal outcome feedback processing error"
        )


@router.get(
    "/api/v1/outcomes/{outcome_id}",
    response_model=OutcomeProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Authoritative Outcome Record"
)
async def get_outcome(
    outcome_id: str,
    merchant_id: str = Query(..., description="Tenant merchant identifier"),
    db: AsyncSession = Depends(get_db)
) -> OutcomeProcessResponse:
    """Fetch immutable outcome record by outcome primary ID."""
    try:
        response = await OutcomeFeedbackService.get_outcome(
            db=db,
            outcome_id=outcome_id,
            merchant_id=merchant_id
        )
        return response
    except ExecutionRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("get_outcome_unhandled_error", outcome_id=outcome_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve outcome record"
        )


@router.get(
    "/api/v1/executions/{execution_id}/outcome",
    response_model=OutcomeProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Authoritative Outcome Record for Execution"
)
async def get_execution_outcome(
    execution_id: str,
    merchant_id: str = Query(..., description="Tenant merchant identifier"),
    db: AsyncSession = Depends(get_db)
) -> OutcomeProcessResponse:
    """Fetch immutable outcome record by execution boundary ID."""
    try:
        response = await OutcomeFeedbackService.get_outcome_by_execution(
            db=db,
            execution_id=execution_id,
            merchant_id=merchant_id
        )
        return response
    except ExecutionRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("get_execution_outcome_unhandled_error", execution_id=execution_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve outcome record for execution"
        )
