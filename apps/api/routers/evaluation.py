"""FastAPI Router for Closed-Loop Learning Evaluation.

Contract: closed-loop-evaluation/v1

Endpoints:
- POST /api/v1/closed-loop-evaluations/run
- GET /api/v1/closed-loop-evaluations/{evaluation_id}
- GET /api/v1/closed-loop-evaluations/{evaluation_id}/curve
- GET /api/v1/closed-loop-evaluations/{evaluation_id}/holdout
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.commerce_service import MerchantNotFoundError
from services.evaluation.schemas import (
    ClosedLoopEvaluationRequest,
    ClosedLoopEvaluationResult,
    LearningCurveCheckpoint,
    HoldoutMetricSet
)
from services.evaluation.service import ClosedLoopEvaluationService
from services.evaluation.errors import (
    ClosedLoopEvaluationError,
    IncompatibleEvaluationVersionError,
    EvaluationNotFoundError,
    EvaluationTenantViolationError,
    EvaluationStateConflictError
)

router = APIRouter(prefix="/api/v1/closed-loop-evaluations", tags=["closed-loop-evaluation"])


@router.post(
    "/run",
    response_model=ClosedLoopEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Execute an immutable closed-loop learning evaluation run"
)
async def run_closed_loop_evaluation(
    request: ClosedLoopEvaluationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute complete closed-loop observe->decide->act->measure->learn evaluation."""
    try:
        return await ClosedLoopEvaluationService.run_evaluation(db, request)
    except IncompatibleEvaluationVersionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except EvaluationTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ClosedLoopEvaluationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/{evaluation_id}",
    response_model=ClosedLoopEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Fetch an evaluation result by ID"
)
async def get_evaluation(
    evaluation_id: str,
    merchant_id: str = Query(..., description="Merchant tenant ID for authorization"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve immutable evaluation record and diagnostics."""
    try:
        return await ClosedLoopEvaluationService.get_evaluation(db, evaluation_id, merchant_id)
    except EvaluationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except EvaluationTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "/{evaluation_id}/curve",
    response_model=List[LearningCurveCheckpoint],
    status_code=status.HTTP_200_OK,
    summary="Fetch learning curve checkpoints for an evaluation run"
)
async def get_learning_curve(
    evaluation_id: str,
    merchant_id: str = Query(..., description="Merchant tenant ID for authorization"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve sequential learning curve checkpoints."""
    try:
        return await ClosedLoopEvaluationService.get_learning_curve(db, evaluation_id, merchant_id)
    except EvaluationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except EvaluationTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "/{evaluation_id}/holdout",
    response_model=HoldoutMetricSet,
    status_code=status.HTTP_200_OK,
    summary="Fetch holdout generalization metrics for an evaluation run"
)
async def get_holdout_metrics(
    evaluation_id: str,
    merchant_id: str = Query(..., description="Merchant tenant ID for authorization"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve holdout generalization metrics evaluated on frozen model."""
    try:
        res = await ClosedLoopEvaluationService.get_evaluation(db, evaluation_id, merchant_id)
        return res.holdout_metrics
    except EvaluationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except EvaluationTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
