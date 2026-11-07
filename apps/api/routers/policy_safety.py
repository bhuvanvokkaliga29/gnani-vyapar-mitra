"""FastAPI Router for Deterministic Policy Safety & Admissibility Gate.

Contract: policy-safety/v1
Endpoints:
- POST /api/v1/policy-safety/validate
- GET /api/v1/policy-safety/{check_id}
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.safety.schemas import PolicySafetyRequest, PolicySafetyResult
from services.safety.service import PolicySafetyService
from services.safety.errors import (
    PolicySafetyError,
    IncompatibleSafetyVersionError,
    MerchantSafetyIsolationError,
    SafetyCheckNotFoundError
)

router = APIRouter(prefix="/api/v1/policy-safety", tags=["policy-safety"])


@router.post(
    "/validate",
    response_model=PolicySafetyResult,
    status_code=status.HTTP_200_OK,
    summary="Validate proposed commercial policy admissibility against fresh merchant state"
)
async def validate_policy(
    request: PolicySafetyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Deterministically check whether a proposed policy satisfies all hard merchant guardrails."""
    try:
        return await PolicySafetyService.validate_policy(db, request)
    except IncompatibleSafetyVersionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MerchantSafetyIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PolicySafetyError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/{check_id}",
    response_model=PolicySafetyResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve auditable policy safety check outcome by ID"
)
async def get_safety_check(
    check_id: str,
    merchant_id: str = Query(..., description="Authoritative merchant ID for tenant verification"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve historical safety check result."""
    try:
        return await PolicySafetyService.get_safety_check(db, check_id, merchant_id)
    except SafetyCheckNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MerchantSafetyIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PolicySafetyError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
