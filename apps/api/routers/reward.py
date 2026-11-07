"""FastAPI router for Phase 8.2 Learning Objective & Reward Layer."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from apps.api.core.database import get_db
from domain.models import LearningEvidenceRecord
from services.learning.service import LearningEvidenceService
from services.reward.schemas import (
    PolicyOpportunityReward,
    AggregatedRewardObjective,
    RewardEvaluationRequest,
    RewardAggregationRequest,
    ObjectiveMetricType
)
from services.reward.calculator import RewardSignalEvaluator
from services.reward.aggregator import ObjectiveAggregator
from services.reward.errors import (
    RewardError,
    ZeroDenominatorError,
    RewardAttributionError
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/reward", tags=["Merchant Policy Learning Reward"])


@router.post("/evaluate-evidence/{evidence_id}", response_model=PolicyOpportunityReward)
async def evaluate_evidence_reward(
    evidence_id: str,
    merchant_id: str = Query(..., description="Authenticated merchant tenant ID"),
    db: AsyncSession = Depends(get_db)
) -> PolicyOpportunityReward:
    """Evaluate an authoritative PolicyLearningEvidence record into a PolicyOpportunityReward."""
    learning_service = LearningEvidenceService()
    evidence = await learning_service.get_evidence(db, evidence_id=evidence_id, merchant_id=merchant_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Learning evidence '{evidence_id}' not found.")

    return RewardSignalEvaluator.evaluate_opportunity(evidence)


@router.post("/aggregate", response_model=AggregatedRewardObjective)
async def aggregate_policy_objective(
    req: RewardAggregationRequest,
    db: AsyncSession = Depends(get_db)
) -> AggregatedRewardObjective:
    """Calculate the aggregated learning objective (Observed Contribution per AI Shopper) for a policy."""
    learning_service = LearningEvidenceService()

    # Query all evidence matching merchant and policy
    conditions = [
        LearningEvidenceRecord.merchant_id == req.merchant_id,
        LearningEvidenceRecord.policy_id == req.policy_id
    ]
    if req.experiment_id:
        conditions.append(LearningEvidenceRecord.experiment_id == req.experiment_id)
    if req.variant:
        conditions.append(LearningEvidenceRecord.variant == req.variant.value)
    if req.buyer_context_key:
        conditions.append(LearningEvidenceRecord.buyer_context_key == req.buyer_context_key)

    stmt = select(LearningEvidenceRecord).where(and_(*conditions))
    records = (await db.execute(stmt)).scalars().all()

    if not records:
        raise HTTPException(
            status_code=400,
            detail="Zero opportunities found matching the specified aggregation criteria."
        )

    evidence_list = [learning_service._record_to_schema(r) for r in records]
    rewards = [RewardSignalEvaluator.evaluate_opportunity(e) for e in evidence_list]

    try:
        return ObjectiveAggregator.aggregate_objective(rewards)
    except ZeroDenominatorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RewardAttributionError as e:
        raise HTTPException(status_code=403, detail=str(e))
