"""FastAPI Router for Constrained Exploration / Exploitation Engine.

Contract: policy-exploration/v1
Endpoints:
- POST /api/v1/policy-exploration/decide
- GET /api/v1/policy-exploration/{decision_id}
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from services.commerce_service import MerchantNotFoundError
from services.exploration.schemas import ExplorationRequest, ExplorationDecision
from services.exploration.service import PolicyExplorationService
from services.exploration.errors import (
    ExplorationError,
    IncompatibleExplorationVersionError,
    MerchantExplorationIsolationError,
    ExplorationDecisionNotFoundError
)

router = APIRouter(prefix="/api/v1/policy-exploration", tags=["policy-exploration"])


@router.post(
    "/decide",
    response_model=ExplorationDecision,
    status_code=status.HTTP_200_OK,
    summary="Deterministically decide between exploiting learned preference or bounded exploration"
)
async def decide_exploration(
    request: ExplorationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Evaluate exploration budget, uncertainty advantage, and Phase 8.6 safety to choose policy."""
    try:
        return await PolicyExplorationService.decide_exploration(db, request)
    except IncompatibleExplorationVersionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MerchantExplorationIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ExplorationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/{decision_id}",
    response_model=ExplorationDecision,
    status_code=status.HTTP_200_OK,
    summary="Retrieve auditable exploration decision by ID"
)
async def get_decision(
    decision_id: str,
    merchant_id: str = Query(..., description="Authoritative merchant ID for tenant verification"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve historical exploration decision result."""
    try:
        return await PolicyExplorationService.get_decision(db, decision_id, merchant_id)
    except ExplorationDecisionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MerchantExplorationIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ExplorationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
