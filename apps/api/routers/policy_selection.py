"""FastAPI Router for Deterministic Learned Candidate Selection.

Contract: policy-selection/v1
Endpoints:
- POST /api/v1/policy-selection/select
- GET /api/v1/policy-selection/{selection_id}
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.selection.schemas import PolicySelectionRequest, PolicySelectionResult
from services.selection.service import PolicySelectionService
from services.selection.errors import (
    PolicySelectionError,
    EmptyCandidateSetError,
    MalformedCandidateError,
    IncompatibleSelectionVersionError,
    SelectionNotFoundError,
    MerchantSelectionIsolationError
)

router = APIRouter(prefix="/api/v1/policy-selection", tags=["policy-selection"])


@router.post(
    "/select",
    response_model=PolicySelectionResult,
    status_code=status.HTTP_200_OK,
    summary="Deterministically select preferred policy candidate under current learning model"
)
async def select_policy(
    request: PolicySelectionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Rank candidate policies by predicted contribution and return preferred policy."""
    try:
        return await PolicySelectionService.select_policy(db, request)
    except (EmptyCandidateSetError, MalformedCandidateError, IncompatibleSelectionVersionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MerchantSelectionIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PolicySelectionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/{selection_id}",
    response_model=PolicySelectionResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve auditable policy selection outcome by ID"
)
async def get_selection(
    selection_id: str,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID for tenant verification"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve historical selection result."""
    try:
        return await PolicySelectionService.get_selection(db, selection_id, merchant_id)
    except SelectionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MerchantSelectionIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
