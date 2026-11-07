"""FastAPI Router for Phase 8.4 Merchant Policy Learning Model."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.core.database import get_db
from services.learning.model_schemas import (
    LearningModelStateSchema,
    ModelPredictionSchema,
    ModelRebuildRequestSchema,
    ModelRebuildResponseSchema,
    CandidatePredictionRequestSchema
)
from services.learning.model_service import PolicyLearningModelService
from services.learning.model_errors import (
    LearningModelError,
    ConcurrentModelUpdateError,
    MerchantModelIsolationError
)

router = APIRouter(prefix="/api/v1/learning/model", tags=["Merchant Policy Learning Model"])


@router.post(
    "/rebuild",
    response_model=ModelRebuildResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Deterministically rebuild a merchant's Contextual LinUCB model from historical memory"
)
async def rebuild_model(
    request: ModelRebuildRequestSchema,
    db: AsyncSession = Depends(get_db)
):
    """Rebuild sufficient statistics by replaying authoritative current-effective observations."""
    try:
        return await PolicyLearningModelService.rebuild_merchant_model(
            db=db,
            merchant_id=request.merchant_id,
            cutoff_time=request.cutoff_time,
            lambda_reg=request.lambda_reg or 1.0,
            alpha_paise=request.alpha_paise or 10000
        )
    except LearningModelError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/predict",
    response_model=ModelPredictionSchema,
    status_code=status.HTTP_200_OK,
    summary="Predict expected contribution, uncertainty, and diagnostic UCB for a candidate policy"
)
async def predict_candidate(
    request: CandidatePredictionRequestSchema,
    db: AsyncSession = Depends(get_db)
):
    """Estimate expected contribution (in paise) and uncertainty for a candidate policy."""
    try:
        return await PolicyLearningModelService.predict_candidate(
            db=db,
            merchant_id=request.merchant_id,
            policy_id=request.policy_id,
            policy_version=request.policy_version or "merchant-policy/v1",
            buyer_context_key=request.buyer_context_key,
            intent=request.intent,
            candidate=request.candidate,
            candidate_snapshot=request.candidate_snapshot
        )
    except LearningModelError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/state",
    response_model=LearningModelStateSchema,
    summary="Inspect current model state parameters and observation count"
)
async def get_model_state(
    merchant_id: str = Query(..., description="Merchant tenant ID"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve metadata and parameters of the merchant's active learning model."""
    from sqlalchemy import select
    from domain.models import PolicyLearningModelState

    stmt = select(PolicyLearningModelState).where(PolicyLearningModelState.merchant_id == merchant_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        # Create cold-start model if none exists
        _, _ = await PolicyLearningModelService.get_or_create_model(db, merchant_id)
        res2 = await db.execute(stmt)
        record = res2.scalar_one()

    return LearningModelStateSchema(
        id=record.id,
        merchant_id=record.merchant_id,
        model_version=record.model_version,
        algorithm_version=record.algorithm_version,
        feature_version=record.feature_version,
        reward_version=record.reward_version,
        formula_version=record.formula_version,
        dimension=record.dimension,
        lambda_reg=float(record.lambda_reg),
        alpha_paise=record.alpha_paise,
        observation_count=record.observation_count,
        version=record.version,
        last_updated_at=record.last_updated_at
    )
