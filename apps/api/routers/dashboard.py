"""FastAPI Router for Phase 10 Merchant AI Control Center.

Contract: dashboard-view/v1

Provides unified, projection-optimized, tenant-isolated read APIs for:
- Overview
- AI Decisions (list & full detail drawer)
- Policies (active & lifecycle version history)
- Experiments
- Learning Center
- Activity (unified audit trail)
- Opportunity Traces
- Authoritative Control Actions (policy promotion & rollback via Phase 8.8)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from apps.api.core.auth import verify_merchant_authorization, verify_caller_scope_for_body
from services.commerce_service import MerchantNotFoundError
from services.audit.errors import AuditTenantViolationError
from services.lifecycle.errors import (
    PolicyLifecycleError,
    MerchantLifecycleIsolationError,
    PolicyVersionNotFoundError,
    ActivePolicyConflictError
)
from services.observability.trace import TraceReconstructionService, OpportunityTraceSchema
from services.dashboard.schemas import (
    DashboardOverviewDTO,
    DecisionListResponseDTO,
    DecisionDetailDTO,
    PolicyManagementDTO,
    ExperimentListResponseDTO,
    LearningCenterDTO,
    ActivityListResponseDTO,
    PolicyPromoteActionRequest,
    PolicyRollbackActionRequest,
    ControlActionResponse
)
from services.dashboard.service import (
    DashboardOverviewService,
    DecisionViewService,
    PolicyViewService,
    ExperimentViewService,
    LearningViewService,
    ActivityViewService
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/dashboard", tags=["Phase 10: Merchant Control Center"])


@router.get("/overview", response_model=DashboardOverviewDTO)
async def get_overview(
    merchant_id: str = Depends(verify_merchant_authorization),
    db: AsyncSession = Depends(get_db)
) -> DashboardOverviewDTO:
    """Retrieve complete overview state for the Merchant AI Control Center."""
    try:
        return await DashboardOverviewService.get_overview(db, merchant_id)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("dashboard_overview_failed", merchant_id=merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load dashboard overview")


@router.get("/decisions", response_model=DecisionListResponseDTO)
async def list_decisions(
    merchant_id: str = Depends(verify_merchant_authorization),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mode: Optional[str] = Query(None, description="Optional filter: EXPLOIT or EXPLORE"),
    execution_status: Optional[str] = Query(None, description="Optional filter: boundary execution status"),
    db: AsyncSession = Depends(get_db)
) -> DecisionListResponseDTO:
    """Retrieve paginated decisions for a merchant tenant."""
    try:
        return await DecisionViewService.list_decisions(
            db=db,
            merchant_id=merchant_id,
            limit=limit,
            offset=offset,
            mode=mode,
            execution_status=execution_status
        )
    except Exception as e:
        logger.error("dashboard_decisions_list_failed", merchant_id=merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list decisions")


@router.get("/decisions/{decision_id}", response_model=DecisionDetailDTO)
async def get_decision_detail(
    decision_id: str,
    merchant_id: str = Depends(verify_merchant_authorization),
    db: AsyncSession = Depends(get_db)
) -> DecisionDetailDTO:
    """Retrieve complete 11-stage lineage and dual-view details for a decision."""
    try:
        return await DecisionViewService.get_decision_detail(db, decision_id, merchant_id)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("dashboard_decision_detail_failed", decision_id=decision_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load decision detail")


@router.get("/policies", response_model=PolicyManagementDTO)
async def get_policies(
    merchant_id: str = Depends(verify_merchant_authorization),
    db: AsyncSession = Depends(get_db)
) -> PolicyManagementDTO:
    """Retrieve active policy and complete version lifecycle history."""
    try:
        return await PolicyViewService.get_policies(db, merchant_id)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("dashboard_policies_failed", merchant_id=merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load policies")


@router.post("/policies/promote", response_model=ControlActionResponse)
async def promote_policy(
    request: PolicyPromoteActionRequest,
    x_caller_merchant_id: Optional[str] = Header(default=None, alias="X-Caller-Merchant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> ControlActionResponse:
    """Safely promote candidate policy via authoritative Phase 8.8 lifecycle service."""
    verify_caller_scope_for_body(request.merchant_id, x_caller_merchant_id, authorization)
    try:
        return await PolicyViewService.promote_policy(db, request)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ActivePolicyConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except MerchantLifecycleIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PolicyLifecycleError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error("dashboard_promote_failed", merchant_id=request.merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Promotion failed: {str(e)}")


@router.post("/policies/rollback", response_model=ControlActionResponse)
async def rollback_policy(
    request: PolicyRollbackActionRequest,
    x_caller_merchant_id: Optional[str] = Header(default=None, alias="X-Caller-Merchant-ID"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> ControlActionResponse:
    """Safely rollback active policy via authoritative Phase 8.8 lifecycle service."""
    verify_caller_scope_for_body(request.merchant_id, x_caller_merchant_id, authorization)
    try:
        return await PolicyViewService.rollback_policy(db, request)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PolicyVersionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ActivePolicyConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except MerchantLifecycleIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PolicyLifecycleError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error("dashboard_rollback_failed", merchant_id=request.merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Rollback failed: {str(e)}")


@router.get("/experiments", response_model=ExperimentListResponseDTO)
async def list_experiments(
    merchant_id: str = Depends(verify_merchant_authorization),
    db: AsyncSession = Depends(get_db)
) -> ExperimentListResponseDTO:
    """Retrieve Phase 7 controlled policy experiments."""
    try:
        return await ExperimentViewService.list_experiments(db, merchant_id)
    except Exception as e:
        logger.error("dashboard_experiments_failed", merchant_id=merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load experiments")


@router.get("/learning", response_model=LearningCenterDTO)
async def get_learning(
    merchant_id: str = Depends(verify_merchant_authorization),
    db: AsyncSession = Depends(get_db)
) -> LearningCenterDTO:
    """Retrieve learning health, context breakdown, and model state."""
    try:
        return await LearningViewService.get_learning_center(db, merchant_id)
    except Exception as e:
        logger.error("dashboard_learning_failed", merchant_id=merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load learning state")


@router.get("/activity", response_model=ActivityListResponseDTO)
async def list_activity(
    merchant_id: str = Depends(verify_merchant_authorization),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
) -> ActivityListResponseDTO:
    """Retrieve unified audit activity log strictly within tenant boundary."""
    try:
        return await ActivityViewService.list_activity(db, merchant_id, limit, offset)
    except AuditTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error("dashboard_activity_failed", merchant_id=merchant_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load activity log")


@router.get("/traces/{opportunity_id}", response_model=OpportunityTraceSchema)
async def get_opportunity_trace(
    opportunity_id: str,
    merchant_id: str = Depends(verify_merchant_authorization),
    db: AsyncSession = Depends(get_db)
) -> OpportunityTraceSchema:
    """Reconstruct complete 8-stage sequence and pinpoint stopping point for an opportunity."""
    try:
        return await TraceReconstructionService.reconstruct_opportunity(
            db=db,
            merchant_id=merchant_id,
            opportunity_id=opportunity_id
        )
    except AuditTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error("dashboard_trace_failed", opportunity_id=opportunity_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reconstruct trace")
