"""FastAPI Router for Phase 8.3 Merchant Policy Memory & Historical Retrieval."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.api.core.database import get_db
from domain.models import LearningEvidenceRecord
from services.learning.service import LearningEvidenceService
from services.experiments.schemas import VariantType
from services.learning.schemas import EvidenceSource
from services.memory.schemas import (
    PolicyMemoryRecordSchema,
    HistoricalObservationFilter,
    HistoricalObservationList,
    HistoricalPolicySummary,
    RecordMemoryRequest
)
from services.memory.service import PolicyMemoryService
from services.memory.errors import MemoryError, MemoryTenantViolationError, MemoryProvenanceError

router = APIRouter(prefix="/api/v1/memory", tags=["Merchant Policy Memory"])


@router.post(
    "/record",
    response_model=PolicyMemoryRecordSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Persist an authoritative learning observation into historical policy memory"
)
async def record_historical_observation(
    request: RecordMemoryRequest,
    db: AsyncSession = Depends(get_db)
):
    """Ingest a validated Phase 8.1 evidence record into immutable historical memory.
    
    The server derives the authoritative reward using Phase 8.2 and commits the record.
    Idempotent: Replaying the same evidence record returns the existing memory record.
    """
    # 1. Fetch authoritative evidence record via LearningEvidenceService
    learning_service = LearningEvidenceService()
    evidence_schema = await learning_service.get_evidence(
        db,
        evidence_id=request.evidence_id,
        merchant_id=request.merchant_id
    )
    if not evidence_schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence record '{request.evidence_id}' not found for merchant '{request.merchant_id}'."
        )

    # 2. Record into immutable memory
    try:
        record = await PolicyMemoryService.record_observation(
            db=db,
            evidence=evidence_schema,
            correction_reason=request.correction_reason,
            reconciliation_ref=request.reconciliation_ref
        )
        return record
    except MemoryTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MemoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{memory_id}",
    response_model=PolicyMemoryRecordSchema,
    summary="Retrieve an individual historical memory record by ID"
)
async def get_historical_observation(
    memory_id: str,
    merchant_id: str = Query(..., description="Merchant tenant ID"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve an individual historical observation with strict tenant isolation."""
    try:
        record = await PolicyMemoryService.get_observation(
            db=db,
            merchant_id=merchant_id,
            memory_id=memory_id
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory record '{memory_id}' not found."
            )
        return record
    except MemoryTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "",
    response_model=HistoricalObservationList,
    summary="Query and retrieve historical policy observations with pagination"
)
async def query_historical_observations(
    merchant_id: str = Query(..., description="Merchant tenant ID"),
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    policy_version: Optional[str] = Query(None, description="Filter by exact policy version"),
    buyer_context_key: Optional[str] = Query(None, description="Filter by buyer context key"),
    experiment_id: Optional[str] = Query(None, description="Filter by experiment ID"),
    variant: Optional[VariantType] = Query(None, description="Filter by variant"),
    evidence_source: Optional[EvidenceSource] = Query(None, description="Filter by source"),
    learning_eligible_only: Optional[bool] = Query(None, description="Filter learning eligible only"),
    is_admissible_only: Optional[bool] = Query(None, description="Filter admissible only"),
    is_current_only: Optional[bool] = Query(None, description="Filter current effective only (True), superseded only (False), or all (None)"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp filter"),
    end_time: Optional[datetime] = Query(None, description="End timestamp filter"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db)
):
    """Deterministically list historical observations with stable ordering (observed_at DESC, id ASC)."""
    filter_params = HistoricalObservationFilter(
        merchant_id=merchant_id,
        policy_id=policy_id,
        policy_version=policy_version,
        buyer_context_key=buyer_context_key,
        experiment_id=experiment_id,
        variant=variant,
        evidence_source=evidence_source,
        learning_eligible_only=learning_eligible_only,
        is_admissible_only=is_admissible_only,
        is_current_only=is_current_only,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )
    return await PolicyMemoryService.query_history(db=db, filter_params=filter_params)


@router.get(
    "/summary/policy",
    response_model=HistoricalPolicySummary,
    summary="Retrieve factual historical summary metrics for a policy"
)
async def get_historical_policy_summary(
    merchant_id: str = Query(..., description="Merchant tenant ID"),
    policy_id: str = Query(..., description="Target policy ID"),
    buyer_context_key: Optional[str] = Query(None, description="Optional context key filter"),
    policy_version: Optional[str] = Query(None, description="Optional policy version filter"),
    is_current_only: bool = Query(True, description="Evaluate current effective records only to prevent double counting"),
    db: AsyncSession = Depends(get_db)
):
    """Compute strictly factual historical aggregates for a policy under a context or merchant-wide.
    
    Contains NO recommendations, NO rankings, and NO decisions.
    """
    return await PolicyMemoryService.get_policy_summary(
        db=db,
        merchant_id=merchant_id,
        policy_id=policy_id,
        buyer_context_key=buyer_context_key,
        policy_version=policy_version,
        is_current_only=is_current_only
    )
