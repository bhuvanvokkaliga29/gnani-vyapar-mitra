"""FastAPI Router for Policy Lifecycle & Promotion Management.

Contracts:
- policy-lifecycle/v1
- promotion-policy/v1

Endpoints:
- POST /api/v1/policy-lifecycle/promote
- POST /api/v1/policy-lifecycle/rollback
- GET /api/v1/policy-lifecycle/active/{merchant_id}
- GET /api/v1/policy-lifecycle/history/{merchant_id}
- GET /api/v1/policy-lifecycle/versions/{merchant_id}
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.commerce_service import MerchantNotFoundError
from services.lifecycle.schemas import (
    PolicyPromotionRequest,
    PolicyPromotionResult,
    PolicyRollbackRequest,
    PolicyRollbackResult,
    ActivePolicyResponse
)
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.errors import (
    PolicyLifecycleError,
    IncompatibleLifecycleVersionError,
    MerchantLifecycleIsolationError,
    PolicyVersionNotFoundError,
    LifecycleTransitionError,
    ActivePolicyConflictError
)

router = APIRouter(prefix="/api/v1/policy-lifecycle", tags=["policy-lifecycle"])


@router.post(
    "/promote",
    response_model=PolicyPromotionResult,
    status_code=status.HTTP_200_OK,
    summary="Evidence-gated promotion of candidate policy to active status"
)
async def promote_policy(
    request: PolicyPromotionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Evaluate evidence, fresh safety, and atomically promote policy version if eligible."""
    try:
        return await PolicyLifecycleService.promote_policy(db, request)
    except IncompatibleLifecycleVersionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MerchantLifecycleIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PolicyLifecycleError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/rollback",
    response_model=PolicyRollbackResult,
    status_code=status.HTTP_200_OK,
    summary="Rollback active policy to a historical version with fresh safety check"
)
async def rollback_policy(
    request: PolicyRollbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """Rollback merchant active policy to a specified historical policy version."""
    try:
        return await PolicyLifecycleService.rollback_policy(db, request)
    except IncompatibleLifecycleVersionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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


@router.get(
    "/active/{merchant_id}",
    response_model=ActivePolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current authoritative active policy version for a merchant"
)
async def get_active_policy(
    merchant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve merchant's single active commercial policy."""
    try:
        return await PolicyLifecycleService.get_active_policy(db, merchant_id)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/history/{merchant_id}",
    response_model=List[PolicyPromotionResult],
    status_code=status.HTTP_200_OK,
    summary="Retrieve chronological lifecycle and promotion transition history"
)
async def get_lifecycle_history(
    merchant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve audit history of all policy promotions, retirements, and rollbacks."""
    try:
        return await PolicyLifecycleService.get_lifecycle_history(db, merchant_id)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/versions/{merchant_id}",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all recorded policy versions and lifecycle states"
)
async def get_policy_versions(
    merchant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all policy versions (CANDIDATE, ACTIVE, RETIRED, ROLLED_BACK)."""
    try:
        return await PolicyLifecycleService.get_policy_versions(db, merchant_id)
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
