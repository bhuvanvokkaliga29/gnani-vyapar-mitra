"""FastAPI Router for Phase 9.4 Observability, Audit & Trace Endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.audit.schemas import AuditQueryResponse, AuditEventRecordSchema
from services.audit.service import AuditService
from services.audit.errors import AuditTenantViolationError, AuditEventNotFoundError
from services.observability.trace import (
    TraceReconstructionService,
    OpportunityTraceSchema,
)

router = APIRouter(prefix="/api/v1/observability", tags=["Phase 9.4: Observability & Audit"])


@router.get("/audit/events", response_model=AuditQueryResponse)
async def query_audit_events(
    merchant_id: str = Query(..., description="Mandatory tenant scope"),
    entity_type: Optional[str] = Query(None, description="Optional entity filter"),
    action: Optional[str] = Query(None, description="Optional action filter"),
    opportunity_id: Optional[str] = Query(None, description="Optional opportunity filter"),
    decision_id: Optional[str] = Query(None, description="Optional decision filter"),
    execution_id: Optional[str] = Query(None, description="Optional execution filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve immutable audit events scoped strictly to the merchant tenant."""
    try:
        return await AuditService.query_events(
            db=db,
            merchant_id=merchant_id,
            entity_type=entity_type,
            action=action,
            opportunity_id=opportunity_id,
            decision_id=decision_id,
            execution_id=execution_id,
            limit=limit,
            offset=offset
        )
    except AuditTenantViolationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/audit/events/{audit_event_id}", response_model=AuditEventRecordSchema)
async def get_audit_event(
    audit_event_id: str,
    merchant_id: str = Query(..., description="Mandatory tenant scope"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a single immutable audit event strictly within tenant scope."""
    try:
        return await AuditService.get_event_by_id(
            db=db,
            audit_event_id=audit_event_id,
            merchant_id=merchant_id
        )
    except AuditTenantViolationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except AuditEventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/trace", response_model=OpportunityTraceSchema)
async def reconstruct_opportunity_trace(
    merchant_id: str = Query(..., description="Mandatory tenant scope"),
    opportunity_id: str = Query(..., description="Mandatory commercial opportunity ID"),
    db: AsyncSession = Depends(get_db)
):
    """Reconstruct the end-to-end trace of an opportunity within strict tenant isolation."""
    try:
        return await TraceReconstructionService.reconstruct_opportunity(
            db=db,
            merchant_id=merchant_id,
            opportunity_id=opportunity_id
        )
    except AuditTenantViolationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
