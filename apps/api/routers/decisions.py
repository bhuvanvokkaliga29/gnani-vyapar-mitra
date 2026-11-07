"""FastAPI Router for Phase 9.1 Canonical Decision Runtime.

Contract: canonical-decision/v1
Endpoints:
- POST /api/v1/decisions/evaluate: Run canonical decision pipeline.
- GET  /api/v1/decisions/{decision_id}: Retrieve immutable DecisionEnvelope.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from services.commerce_service import MerchantNotFoundError
from services.runtime.schemas import (
    CanonicalDecisionRequest,
    DecisionEnvelope
)
from services.runtime.service import CanonicalDecisionRuntime
from services.runtime.errors import (
    IncompatibleRuntimeVersionError,
    DecisionNotFoundError,
    DecisionTenantViolationError,
    MissingBuyerIntentInputError,
    MerchantInactiveError
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/decisions", tags=["Canonical Decisions"])


@router.post(
    "/evaluate",
    response_model=DecisionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Evaluate shopping opportunity through Canonical Decision Runtime"
)
async def evaluate_decision(
    request: CanonicalDecisionRequest,
    db: AsyncSession = Depends(get_db)
) -> DecisionEnvelope:
    """Execute end-to-end Canonical Decision pipeline and return an immutable DecisionEnvelope."""
    try:
        return await CanonicalDecisionRuntime.decide(db, request)
    except IncompatibleRuntimeVersionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MissingBuyerIntentInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MerchantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MerchantInactiveError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error("canonical_decision_evaluation_failed", error=str(e), merchant_id=request.merchant_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Decision evaluation failed: {str(e)}")


@router.get(
    "/{decision_id}",
    response_model=DecisionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve immutable DecisionEnvelope by ID"
)
async def get_decision(
    decision_id: str,
    merchant_id: str = Query(..., description="Requesting merchant tenant ID for authorization"),
    db: AsyncSession = Depends(get_db)
) -> DecisionEnvelope:
    """Retrieve an immutable DecisionEnvelope by ID with strict tenant boundary enforcement."""
    try:
        return await CanonicalDecisionRuntime.get_decision(db, decision_id, merchant_id)
    except DecisionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DecisionTenantViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error("canonical_decision_retrieval_failed", error=str(e), decision_id=decision_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Decision retrieval failed: {str(e)}")
